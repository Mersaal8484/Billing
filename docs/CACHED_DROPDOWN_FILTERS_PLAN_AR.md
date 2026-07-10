# خطة تفعيل الفلاتر كـ Cached Dropdown Selection في Utility ERP

## الهدف

توحيد الفلاتر المرتبطة في الواجهات والـ wizards بحيث لا يعتمد المستخدم على dropdowns عامة أو دومينات متكررة ومكلفة، بل على قوائم اختيار محسوبة ومخزنة مؤقتا داخل السجل الحالي أو في خدمة مركزية قابلة لإعادة الاستخدام.

المقصود بـ Cached Dropdown Selection هنا:

- حقل مساعد `available_*_ids` يحسب الخيارات المسموحة مرة واحدة حسب الحقول المؤثرة.
- الـ dropdown يستخدم `domain="[('id', 'in', available_*_ids)]"` بدلا من دومين طويل مكرر في XML أو onchange.
- عند تغير الحقول المؤثرة يتم تصفير الاختيار غير الصالح واقتراح قيمة افتراضية صحيحة إن وجدت.
- القيود `@api.constrains` تبقى خط الدفاع النهائي؛ الكاش لتحسين UX والأداء وليس بديلا عن التحقق.

## نطاق العمل

النطاق يشمل الأماكن التي تعتمد على اختيارات مترابطة:

1. تسجيل المشترك `utility.customer.wizard`.
2. حساب المشترك `utility.customer`.
3. قوالب العقود `utility.contract.template` واختيارها حسب التصنيف والمنطقة.
4. العدادات ومنتجات العدادات `utility.meter`, `utility.meter.model`, `product.product`.
5. مناطق NUTS: region, area, zone, office, substation, feeder, transformer, route.
6. استبدال العداد `utility.meter.replace.wizard` وطلبات العمليات التي تختار عدادا أو محولا أو مسارا.
7. مخزون العدادات `utility.inventory.item` عند ربط المنتج بالرقم التسلسلي/lot.

خارج النطاق مبدئيا:

- APIs العامة في `utility_portal` إلا إذا احتاجت نفس خدمة الدومينات لاحقا.
- تغيير قواعد الصلاحيات أو record rules.
- إدخال mail أو email؛ لا يستخدم في هذا المشروع.

## المشكلة الحالية

توجد عدة أنماط متفرقة:

- دومينات XML مباشرة مثل `subscriber_id` حسب `category_id`.
- onchanges ترجع domain في Python مثل اختيار قالب العقد.
- دومينات طويلة تتكرر في الويزارد والنموذج.
- بعض الحقول تحتاج قوائم مشتقة مثل منتجات العدادات من `utility.meter.model.product_id`.
- عند تغير field مؤثر قد يبقى اختيار قديم غير صالح حتى الحفظ.
- بعض الخيارات كثيرة العدد مثل العدادات والعملاء والمنتجات، ما يجعل البحث العام بطيئا وغير دقيق.

## التصميم القياسي المقترح

### 1. نمط الحقول المساعدة

لكل dropdown مهم نضيف حقلا مساعدا:

```python
available_contract_template_ids = fields.Many2many(
    'utility.contract.template', compute='_compute_available_contract_template_ids')
contract_template_id = fields.Many2one(
    'utility.contract.template', domain="[('id', 'in', available_contract_template_ids)]")
```

نفس النمط يطبق على:

- `available_subscriber_ids`
- `available_contract_template_ids`
- `available_area_ids`
- `available_zone_ids`
- `available_route_ids`
- `available_meter_product_ids`
- `available_meter_model_ids`
- `available_meter_ids`
- `available_transformer_ids`
- `available_feeder_ids`
- `available_lot_ids`

### 2. فصل منطق الدومين عن الواجهة

أي دومين عمل حقيقي يجب أن يكون في Python helper:

```python
def _get_contract_template_domain(self):
    ...
```

والـ XML يستخدم فقط `available_*_ids`.

السبب: نفس المنطق يستخدم في form, wizard, constraints, default selection, APIs لاحقا.

### 3. تصفير الاختيارات غير الصالحة

عند تغير field مؤثر:

```python
if rec.contract_template_id not in rec.available_contract_template_ids:
    rec.contract_template_id = False
```

ثم اختيار default إن كان آمنا:

```python
if not rec.contract_template_id and len(rec.available_contract_template_ids) == 1:
    rec.contract_template_id = rec.available_contract_template_ids[:1]
```

لا نختار افتراضيا إذا كانت الخيارات كثيرة إلا في حالات معروفة مثل default contract template على نوع المشترك.

### 4. قواعد الأداء

- تجنب `search()` داخل loop على كل سجل إذا كانت نفس الدومينات قابلة للتجميع.
- للـ TransientModel يمكن قبول compute بسيط، لكن للـ models الدائمة يفضل helper + onchange أو compute غير مخزن.
- الحقول المستخدمة في الدومينات يجب أن تكون indexed عندما تكون على نماذج كبيرة:
  - `utility.customer.region_id`, `area_id`, `route_id`, `meter_id`
  - `utility.meter.customer_id`, `serial_number`, `meter_number`, `transformer_id`, `feeder_id`
  - `utility.contract.template.active`, `scope`, `pricing_mode`
- لا نخزن Many2many cached fields في قاعدة البيانات إلا إذا ثبت وجود حمل كبير؛ الافتراضي `store=False`.

## خريطة الأماكن المقترحة

| المكان | الحقول المؤثرة | dropdown الهدف | الكاش المقترح | الأولوية |
|---|---|---|---|---|
| `utility.customer.wizard` | `category_id` | `subscriber_id` | `available_subscriber_ids` | عالية |
| `utility.customer.wizard` | category/subscriber/region/area | `contract_template_id` | `available_contract_template_ids` | عالية |
| `utility.customer.wizard` | meter product setup | `meter_product_id` | `available_meter_product_ids` | عالية |
| `utility.customer.wizard` | `meter_product_id` | `meter_model_id`, `meter_type_id` | `available_meter_model_ids` | عالية |
| `utility.customer.wizard` | region/area/zone | `route_id` | `available_route_ids` | متوسطة |
| `utility.customer` | category/subscriber/region/area | `contract_template_id` | `available_contract_template_ids` | عالية |
| `utility.customer` | area/route/transformer | `meter_id`, `cell_id`, `transformer_id` | `available_meter_ids`, `available_transformer_ids` | متوسطة |
| `utility.meter.replace.wizard` | account/current meter | `new_meter_id` | `available_new_meter_ids` | عالية |
| `utility.inventory.item` | `product_id` | `lot_id` | `available_lot_ids` | متوسطة |
| operations service orders | service type/customer | meter/transformer/route | حسب نوع الخدمة | متوسطة |

## مراحل التنفيذ

### المرحلة 1: تثبيت نمط موحد في تسجيل المشترك

ملفات العمل:

- `utility_core/wizards/utility_customer_wizard.py`
- `utility_core/views/utility_customer_wizard_views.xml`

المطلوب:

1. إضافة `available_subscriber_ids` وربط `subscriber_id` بها.
2. إضافة `available_contract_template_ids` وربط `contract_template_id` بها.
3. تحويل `available_meter_product_ids` الحالي إلى نفس النمط الرسمي.
4. إضافة تصفير تلقائي للقيم غير الصالحة عند تغير التصنيف أو الموقع أو المنتج.
5. إبقاء constraints الحالية كتحقق نهائي.

معايير القبول:

- تغيير الفئة يغير أنواع المشتركين المتاحة فقط.
- تغيير المنطقة/الفرع يغير قوالب العقد المتاحة فقط.
- لا يمكن اختيار قالب عقد غير مناسب من الواجهة.
- إذا تم تمرير قيمة غير صالحة برمجيا، constraint يمنع الحفظ.

### المرحلة 2: تطبيق نفس النمط على `utility.customer`

ملفات العمل:

- `utility_core/models/utility_customer.py`
- `utility_core/views/utility_customer_views.xml`

المطلوب:

1. نقل منطق `_get_contract_template_domain()` إلى helper قابل لإعادة الاستخدام.
2. إضافة `available_contract_template_ids` على نموذج الحساب.
3. ربط form field بالدومين المختصر.
4. تصفير القالب إذا تغير التصنيف أو المنطقة وأصبح غير صالح.

معايير القبول:

- شاشة الحساب لا تعرض قوالب غير متوافقة.
- التعديل اليدوي أو الاستيراد لا يتجاوز القيود.

### المرحلة 3: خدمة مشتركة للدومينات المتكررة

الخيار المحافظ:

- إضافة mixin بسيط في `utility_core/models/utility_dropdown_mixin.py` بدون نموذج جديد.

الخيار الأوسع:

- إضافة service model غير مخزن مثل `utility.dropdown.service` يحوي helpers فقط.

الوظائف المقترحة:

```python
_get_subscriber_domain(category)
_get_contract_template_domain(category, subscriber, region, area)
_get_route_domain(region, area, zone)
_get_meter_product_domain()
_get_available_new_meter_domain(account)
```

معايير القبول:

- لا يتكرر دومين قالب العقد في أكثر من مكان.
- أي تعديل مستقبلي على قواعد القالب يتم في helper واحد.

### المرحلة 4: العدادات والمخزون والاستبدال

ملفات العمل:

- `utility_operations/wizards/meter_replace_wizard.py`
- `utility_operations/views/meter_replace_views.xml`
- `utility_inventory/models/utility_inventory_item.py`
- `utility_inventory/views/utility_inventory_item_views.xml`

المطلوب:

1. `available_new_meter_ids` لاستبدال العداد، بدلا من دومين عام مباشر.
2. فلترة العدادات الجديدة حسب:
   - غير مرتبطة بعميل.
   - نشطة.
   - نفس الشركة.
   - يفضل نفس payment type/phase إن توفرت.
3. `available_lot_ids` في المخزون حسب المنتج والموقع والحالة.
4. ربط منتج العداد بالموديل والـ lot عند الإمكان.

معايير القبول:

- استبدال العداد لا يعرض عدادات مرتبطة بمشتركين آخرين.
- اختيار المنتج في المخزون لا يعرض serials لمنتجات أخرى.

### المرحلة 5: NUTS والعمليات الميدانية

ملفات العمل تحدد بعد مراجعة service orders وviews المرتبطة.

المطلوب:

1. `available_area_ids` حسب region.
2. `available_zone_ids` حسب area.
3. `available_substation_ids` حسب zone.
4. `available_feeder_ids` حسب substation/zone.
5. `available_transformer_ids` حسب feeder/zone.
6. `available_route_ids` حسب area/zone.

معايير القبول:

- المستخدم لا يرى عناصر خارج التسلسل الجغرافي المختار.
- تغيير أي مستوى أعلى يمسح المستويات الأدنى غير الصالحة.

## قواعد UX المطلوبة

- لا تعرض حقولا تقنية مثل `available_*_ids` إلا invisible.
- استخدم `options="{'no_create': True, 'no_open': True}"` في الويزاردات لمنع إنشاء بيانات مرجعية بالخطأ.
- استخدم labels عملية:
  - `منتج العداد`
  - `موديل العداد`
  - `الرقم التسلسلي`
  - `قالب العقد المناسب`
- لا تجعل المستخدم يدخل رقم العداد يدويا؛ يظل من sequence.
- إذا لم توجد خيارات، تظهر رسالة Validation واضحة عند الحفظ أو warning في onchange.

## قواعد الأمان والصحة

- لا تستخدم `sudo()` في حساب خيارات dropdown إلا إذا كان المطلوب عرض خيارات إعدادات عامة لا يملك المستخدم حق قراءتها، وهذا يحتاج تعليق واضح.
- الكاش لا يغني عن القيود.
- كل `create/write` حساس يجب أن يعيد التحقق:
  - قالب العقد مناسب للتصنيف والمنطقة.
  - العداد/serial غير مستخدم.
  - المنتج مرتبط بموديل عداد.
  - route/transformer ضمن نفس المنطقة.

## اختبارات مقترحة لاحقا

عند إضافة بنية tests:

1. `TransactionCase` لتسجيل مشترك بفئة ومنطقة وقالب صحيح.
2. فشل تسجيل مشترك بقالب لا يدعم الفئة.
3. فشل تسجيل مشترك بقالب لا يدعم المنطقة.
4. اختيار منتج عداد يولد عدادا برقم sequence وserial صحيح.
5. فشل تكرار serial.
6. تغيير المنطقة يمسح route/contract template غير المناسبين.
7. استبدال العداد لا يقبل عدادا مرتبطا بعميل آخر.

## ترتيب التنفيذ المقترح

1. إنهاء `utility.customer.wizard` لأنه أعلى نقطة إدخال وتأثيره مباشر.
2. توحيد `utility.customer` مع نفس helpers.
3. استخراج helper مشترك لقوالب العقود والتصنيف.
4. ضبط العدادات والاستبدال والمخزون.
5. توسيع NUTS والعمليات الميدانية.
6. إضافة فحوص syntax/XML بعد كل مرحلة.
7. تحديث docs وقائمة قبول المستخدم.

## ملاحظات خاصة بالمشروع الحالي

- لا توجد tests جاهزة؛ التحقق الفوري يكون عبر `ast.parse` و`xml.etree.ElementTree.parse`.
- `py_compile` قد يفشل بسبب صلاحيات `__pycache__` في Windows، لذلك لا يعتمد عليه هنا.
- يجب عدم تشغيل `odoo-test` حاليا حسب تعليمات المشروع.
- يوجد بالفعل اتجاه صحيح في `utility.customer.wizard` لاختيار منتج العداد وربطه بموديل العداد، ويجب تعميم النمط نفسه بدلا من إبقائه حالة منفردة.

## إضافة خاصة: فترات القراءة والفوترة المفتوحة حسب العقد والمنطقة

يجب إضافة هذا البند إلى تنفيذ cached dropdowns لأنه مرتبط مباشرة بالفواتير والقراءات.

### الهدف

عند اختيار الفترة في القراءات أو الفواتير يجب ألا تظهر كل الفترات، بل تظهر فقط الفترات المفتوحة المناسبة حسب:

- نوع العمل: قراءات `readings` للفترات المستخدمة في القراءة والفوترة.
- حالة الفترة: الفترة المفتوحة/النشطة `is_current_period=True`.
- نوع العقد: `contract_template_id.recurring_rule_type` مثل شهري، نصف شهري، ربع سنوي، سنوي.
- المنطقة: `region_id.recurring_rule_type` أو `area_id.recurring_rule_type` إذا كانت سياسة المنطقة تحدد دورة مختلفة.
- الحساب/المشترك: لأن نوع العقد والمنطقة يؤخذان من `utility.customer`.

### الحقول المقترحة

في `utility.reading`:

```python
available_open_reading_period_ids = fields.Many2many(
    'date.range', compute='_compute_available_open_reading_period_ids')
```

في `sale.order` لفواتير الكهرباء:

```python
available_billing_period_ids = fields.Many2many(
    'date.range', compute='_compute_available_billing_period_ids')
```

في `utility.reading.batch`:

```python
available_open_reading_period_ids = fields.Many2many(
    'date.range', compute='_compute_available_open_reading_period_ids')
```

### الدومين القياسي

```python
def _get_open_reading_period_domain(self, account=False, region=False, area=False):
    billing_period = False
    if account and account.contract_template_id:
        billing_period = account.contract_template_id.recurring_rule_type
    if not billing_period and area and area.recurring_rule_type:
        billing_period = area.recurring_rule_type
    if not billing_period and region and region.recurring_rule_type:
        billing_period = region.recurring_rule_type

    domain = [
        ('is_current_period', '=', True),
        ('work_type', '=', 'readings'),
    ]
    if billing_period:
        domain.append(('billing_period', '=', billing_period))
    return domain
```

### ربط الواجهة

في شاشات القراءات والفواتير والدفعات يجب أن يكون حقل `date_range_id` بهذا النمط:

```xml
<field name="available_open_reading_period_ids" invisible="1"/>
<field name="date_range_id" domain="[('id', 'in', available_open_reading_period_ids)]"/>
```

وفي الفواتير:

```xml
<field name="available_billing_period_ids" invisible="1"/>
<field name="date_range_id" domain="[('id', 'in', available_billing_period_ids)]"/>
```

### ملاحظة مهمة حول المناطق

قيد `date.range` الحالي يمنع أكثر من فترة نشطة لنفس `billing_period + work_type` على مستوى النظام كله. إذا كانت كل منطقة تحتاج فترة مفتوحة مستقلة، مثلا منطقة شهرية ومنطقة نصف شهرية أو أكثر من منطقة بنفس الدورة لكن بفترات مختلفة، يجب توسيع `date.range` بإضافة نطاق جغرافي:

- `region_ids` على `date.range`.
- `area_ids` على `date.range`.
- تعديل قيد الفترة النشطة ليصبح حسب `billing_period + work_type + region/area`.
- تعديل `action_set_as_current()` ليغلق الفترات داخل نفس النطاق الجغرافي فقط.

### الملفات المعنية

- `utility_core/models/utility_date_range.py`
- `utility_core/views/utility_date_range_views.xml`
- `utility_core/models/utility_reading.py`
- `utility_billing/models/utility_reading.py`
- `utility_billing/models/utility_sale_order.py`
- `utility_billing/models/utility_reading_batch.py`
- `utility_billing/views/utility_reading_views.xml`
- `utility_billing/views/utility_sale_order_views.xml`
- `utility_billing/views/utility_reading_batch_views.xml`

### معايير القبول

- عقد شهري لا يعرض إلا فترة قراءة شهرية مفتوحة.
- عقد نصف شهري لا يعرض إلا فترة قراءة نصف شهرية مفتوحة.
- إذا كانت المنطقة تضبط دورة فوترة مختلفة، تدخل في الفلترة قبل عرض الفترة.
- الفاتورة الناتجة من القراءة تستخدم نفس `date_range_id` المناسب.
- دفعة القراءات لا تقبل فترة دفع أو فترة غير مفتوحة للقراءات.
- إذا لا توجد فترة مناسبة، تظهر رسالة واضحة: لا توجد فترة قراءة مفتوحة مناسبة لدورة العقد والمنطقة.

### أولوية التنفيذ

هذه الإضافة يجب تنفيذها بعد تثبيت cached dropdowns في `UtilityCustomerWizard` و`utility.customer` مباشرة، وقبل التوسع في NUTS والعمليات الميدانية، لأنها تؤثر على صحة الفاتورة والقراءة.
