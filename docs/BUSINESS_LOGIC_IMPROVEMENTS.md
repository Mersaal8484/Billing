# ملاحظات تحسين منطق الأعمال
> بدءًا من 2026-07-04

## 1. الفيدرات (Feeders)

### 1.1 عداد المقارنة = عداد الربط والرصد

**المشكلة:** يوجد حقلان منفصلان في نموذج `utility.feeder`:
- `coupling_meter_id` (عداد الربط الرئيسي)
- `comparison_meter_ids` (عدادات المقارنة)

**التحليل:** من حيث المبدأ، عداد المقارنة هو نفسه عداد الربط والرصد. لا يوجد مبرر عملي لفصلها إلى حقلين مختلفين.

**الإجراء المطلوب:**
- دمج `comparison_meter_ids` مع `coupling_meter_id` في حقل واحد (Many2one أو One2many).
- إزالة جدول العلاقة `feeder_comparison_meter_rel`.
- تبسيط الواجهة بحيث يظهر فقط عداد ربط واحد للفيدر.

### 1.2 إزالة عرض المشتركين من الفيدر

**المشكلة:** صفحة "عقود المشتركين" (`cell_account_ids`) في نموذج الفيدر تعرض المشتركين المرتبطين مباشرة بالفيدر/الخلية.

**التحليل:** في النموذج الحالي، المشتركون يتبعون المحول (`utility.transformer`) وليس الفيدر. ربط المشترك مباشرة بالفيدر (عبر `cell_id`) ينطبق فقط على الخلايا الخاصة (private cells) حيث الفيدر هو نفسه المحول ولا يوجد محول وسيط. في الحالة العامة، المشترك يتبع المحول والمحول يتبع الفيدر، لذا عرض المشتركين على الفيدر يسبب:
- تضليلًا في هرمية الشبكة (المشترك ← محول ← فيدر).
- تكرارًا للمعلومات لأنها تظهر أيضًا في المحول.

**الإجراء المطلوب:**
- إزالة صفحة "عقود المشتركين" من نموذج الفيدر.
- إزالة حقل `cell_account_ids` إذا لم يعد مستخدمًا في أي منطق آخر.
- الإبقاء على إمكانية تصفح المشتركين عبر زر ذكي يفتح `utility.customer` مع فلتر `('cell_id', '=', current_id)` عند الحاجة.

### 1.3 إزالة ربط الفيدر بـ Zone

**المشكلة:** الفيدر مرتبط بـ `zone_id` (`utility.region` بنوع `zone`).

**التحليل:** الفيدر ينتمي إلى محطة (`substation_id`)، والمحطة بدورها ترتبط بالمنطقة عبر التسلسل الهرمي NUTS. ربط الفيدر مباشرة بـ `zone_id`:
- يخلق ازدواجية في الموقع الهرمي (الفيدر ← محطة ← منطقة).
- يزيد من احتمالية عدم الاتساق (مثلاً: zone_id مختلف عن substation_id.zone_id).
- المنطقة متاحة أصلاً عبر `substation_id` ← `zone_id`.

**الإجراء المطلوب:**
- إزالة حقل `zone_id` من `utility.feeder`.
- جعل `zone_id` محسوبًا من `substation_id.zone_id` أو `region_id` parent chain عند الحاجة.
- تعديل القيد `unique(code, zone_id)` ليكون `unique(code, substation_id)`.

### 1.4 إزالة عرض جميع عدادات الفيدر

**المشكلة:** صفحة "جميع عدادات الفيدر" (`meter_ids`) في نموذج الفيدر تعرض One2many لجميع العدادات المرتبطة.

**التحليل:** العدادات في الفيدر هي:
- عداد الربط الرئيسي (مهم ومعروض في القسم المخصص).
- عدادات المشتركين (التي تتبع المحولات التابعة للفيدر، وليس الفيدر مباشرة).

عرض كل العدادات دفعة واحدة بدون تصنيف (عدادات ربط vs عدادات مشتركين) يشتت المستخدم ولا يضيف قيمة عملية.

**الإجراء المطلوب:**
- إزالة `meter_ids` من واجهة الفيدر.
- الإبقاء فقط على `coupling_meter_id` (عداد الربط) مع إمكانية الانتقال إلى عدادات المحولات التابعة عبر زر.
- إذا احتيج إلى عرض عدادات المشتركين، يتم ذلك عبر زر ذكي يفتح `utility.meter` مع فلتر `('feeder_id', '=', current_id)`.

## 2. الفترات والمناطق (Date Ranges & Regions)

### 2.1 الربط الوهمي بين الفترات والمناطق عبر نوع الفوترة

**المشكلة:** لا يوجد رابط مباشر أو غير مباشر بين `date.range` (الفترات الزمنية) و `utility.region` (المناطق). كل نموذج يعيش بشكل مستقل:

| النموذج | الحقل | المصدر |
|---------|-------|--------|
| `date.range` | `billing_period` | `BILLING_PERIOD_TYPES` (في `utility_date_range.py`) |
| `utility.region` | `recurring_rule_type` | نفس `BILLING_PERIOD_TYPES` (في `utility_region.py`) |
| `utility.contract.template` | `recurring_rule_type` | نفس القيم |

**التحليل:** العلاقة بين المنطقة والفترات الزمنية هي علاقة غير مباشرة (virtual) تعبر عن طريق:
1. المنطقة لها `recurring_rule_type` (شهري، نصف شهري، إلخ).
2. الفترة (date.range) لها `billing_period` (نفس الأنواع).
3. قالب العقد (`contract.template`) له `recurring_rule_type` والذي يُستخدم في `_get_billing_period_type()` للبحث عن الفترة المناسبة (انظر `utility_billing/models/utility_reading.py:_get_current_billing_date_range()`).

**المشاكل الحالية:**
1. لا يوجد حقل `region_id` في `date.range` لربط الفترة بالمنطقة التي تنتمي إليها.
2. لا يوجد One2many في `utility.region` يعرض الفترات المرتبطة بها.
3. البحث عن الفترة الحالية يتم فقط عبر `billing_period` بدون تحديد المنطقة، مما يعني:
   - إذا كان هناك منطقتان بنفس `recurring_rule_type` (مثلاً: منطقتان شهريتان)، فسيتم إرجاع أول `is_current_period` فقط بدون تمييز.
   - لا يمكن أن يكون لكل منطقة فترتها النشطة المستقلة.
4. عند إنشاء فاتورة من قراءة (في `action_generate_bill`)، يتم البحث عن `is_current_period` بدون مراعاة منطقة المشترك (`account_id.area_id` أو `account_id.region_id`).

**الإجراء المطلوب:**
1. إضافة حقل `region_id` إلى `date.range` (Many2one إلى `utility.region`) اختياري.
2. إضافة حقل `date_range_ids` في `utility.region` (One2many معكوس).
3. تعديل `_get_current_billing_date_range()` لترشيح الفترات حسب منطقة المشترك:
   ```python
   domain = [
       ('is_current_period', '=', True),
       ('work_type', '=', 'readings'),
       ('billing_period', '=', billing_period),
       ('region_id', 'in', [account.area_id.id, account.region_id.id, False]),
   ]
   ```
4. تعديل قيد `_check_single_active_period()` ليشمل `region_id`:
   - فترة نشطة لكل منطقة + billing_period + work_type (وليس فترة نشطة واحدة فقط للنظام بأكمله).
   - السماح بفترة نشطة بدون `region_id` كقيمة افتراضية عامة.
5. توحيد تسمية الحقل: استخدام `recurring_rule_type` أو `billing_period` في كل من `date.range` و `utility.region` لتعكس نفس المفهوم.

## 3. اسم العداد (Meter Display Name)

### 3.1 إضافة اسم المشترك/المحول/الفيدر إلى اسم العداد

**المشكلة:** حقل `_rec_name` في `utility.meter` هو `meter_number` فقط (السطر 12 في `utility_meter.py`). عند اختيار عداد من قائمة Many2one المنسدلة، يظهر فقط رقم العداد (مثلاً `MTR-00123`) بدون سياق.

**التحليل:** يحتاج المستخدم إلى تمييز العداد بسرعة عند الاختيار من القائمة. يجب أن يظهر اسم العداد مركّباً حسب الأولوية:
- إذا كان للعداد مشترك: `[MTR-00123] - محمد أحمد`
- إذا كان للعداد محول: `[MTR-00123] - محول خاص 1`
- إذا كان للعداد فيدر: `[MTR-00123] - فيدر رئيسي`
- وإلا: `[MTR-00123]` فقط

**الإجراء المطلوب:**
- إضافة override لدالة `name_get()` في `utility.meter` ترجع اسماً مركّباً حسب الأولوية:
  ```python
  def name_get(self):
      result = []
      for meter in self:
          name = f"[{meter.meter_number}]"
          if meter.customer_id and meter.customer_id.partner_id:
              name += f" - {meter.customer_id.partner_id.name}"
          elif meter.transformer_id:
              name += f" - {meter.transformer_id.name}"
          elif meter.feeder_id:
              name += f" - {meter.feeder_id.name}"
          result.append((meter.id, name))
      return result
  ```
- ملاحظة: `_rec_name = 'meter_number'` سيظل يعمل مع `name_get()` override. لا حاجة لإزالته، لكن `name_get` له الأولوية على `_rec_name` في Odoo.
- بديل: استخدام `_compute_display_name` (متوفر في Odoo 16) مع `@api.depends` يشمل `meter_number`, `customer_id`, `customer_id.partner_id.name`, `transformer_id.name`, `feeder_id.name`.

## 4. مسار القراءة (Utility Route)

### 4.1 جعل جدول المشتركين في المسار للقراءة فقط مع ويزرات إضافة/حذف

**المشكلة:** حقل `customer_ids` في `utility.route` هو One2many عادي يُعرض كـ inline tree قابل للتعديل المباشر (إضافة/حذف/تعديل مشتركين من داخل فورم المسار).

**التحليل:** المسار (`utility.route`) هو تجميع للمشتركين بناءً على موقعهم الجغرافي لأغراض القراءة الميدانية والتحصيل. يجب أن يكون المسار للقراءة فقط لمنع التعديل العشوائي على توزيع المشتركين. إضافة/حذف مشترك من المسار يجب أن تكون عبر ويزرات مخصصة تضمن:
- تسجيل تاريخ الإضافة/الحذف.
- التحقق من أن المشترك لا ينتمي لمسار آخر.
- منع حذف مشترك لديه قراءات معلقة في المسار الحالي.

**الإجراء المطلوب:**
1. **جعل `customer_ids` للقراءة فقط** في فورم المسار:
   - إضافة `readonly="1"` أو `attrs="{'readonly': [('active', '=', True)]}"` على `<field name="customer_ids">` في الواجهة.
   - بدلاً من `editable="bottom"`، يبقى `tree` عادي بدون `editable`.

2. **إنشاء ويزر "إضافة مشتركين إلى المسار"**:
   - نموذج عابر (`TransientModel`) باسم `utility.route.add.customer.wizard`.
   - يحتوي على حقل `route_id` (Many2one إلى `utility.route`) و `customer_ids` (Many2many إلى `utility.customer`).
   - فلتر: فقط المشتركين الذين ليس لديهم `route_id` أو `route_id` فارغ.
   - زر `action_add()`:
     ```python
     def action_add(self):
         self.route_id.write({
             'customer_ids': [(4, c.id) for c in self.customer_ids]
         })
     ```
   - يعرض نافذة منبثقة لاختيار المشتركين.

3. **إنشاء ويزر "حذف مشتركين من المسار"**:
   - نموذج عابر باسم `utility.route.remove.customer.wizard`.
   - يحتوي على حقل `route_id` (readonly) و `customer_ids` (Many2many إلى `utility.customer`).
   - فلتر: فقط المشتركين الذين `route_id` = المسار الحالي.
   - زر `action_remove()`:
     ```python
     def action_remove(self):
         self.route_id.write({
             'customer_ids': [(3, c.id) for c in self.customer_ids]
         })
     ```

4. **إضافة أزرار في فورم المسار**:
   - زر "إضافة مشتركين" في header أو فوق جدول المشتركين يستدعي `action_add_customers_wizard()`.
   - زر "حذف مشتركين" بجانبه.
   - إجراءات (actions):
     ```python
     def action_add_customers_wizard(self):
         return {
             'type': 'ir.actions.act_window',
             'name': 'إضافة مشتركين',
             'res_model': 'utility.route.add.customer.wizard',
             'view_mode': 'form',
             'target': 'new',
             'context': {'default_route_id': self.id},
         }
     
     def action_remove_customers_wizard(self):
         return {
             'type': 'ir.actions.act_window',
             'name': 'حذف مشتركين',
             'res_model': 'utility.route.remove.customer.wizard',
             'view_mode': 'form',
             'target': 'new',
             'context': {'default_route_id': self.id},
         }
     ```

### 4.2 دعم عدة كشافين ومحصلين لكل مسار

**المشكلة:** الحقول الحالية في `utility.route`:
- `inspector_id` — Many2one (كشاف واحد فقط)
- `cashier_id` — Many2one (محصل واحد فقط)
- `supervisor_id` — Many2one (مشرف واحد فقط)

**التحليل:** المسار الواحد قد يخدم عدة مناطق فرعية أو أحياء، مما يتطلب:
- أكثر من كشاف لقراءة العدادات في نفس المسار (خاصة للمسارات الكبيرة).
- أكثر من محصل لتحصيل الفواتير (مثلاً: محصل للقطاع السكني وآخر للقطاع التجاري في نفس المسار).

الحقول `inspector_id` و `cashier_id` من نوع Many2one تحد من التعيين إلى شخص واحد فقط.

**الإجراء المطلوب:**
1. **تغيير `inspector_id` إلى `inspector_ids`** من Many2one إلى Many2many:
   ```python
   inspector_ids = fields.Many2many(
       'utility.staff', 'route_inspector_rel', 'route_id', 'staff_id',
       string='الكشافون',
       domain="[('user_role_id.code', '=', 'inspector')]",
   )
   ```

2. **تغيير `cashier_id` إلى `cashier_ids`**:
   ```python
   cashier_ids = fields.Many2many(
       'utility.staff', 'route_cashier_rel', 'route_id', 'staff_id',
       string='المحصلون',
       domain="[('user_role_id.code', '=', 'cashier')]",
   )
   ```

3. **تحديث الواجهة** (`utility_route_views.xml`):
   - استبدال `<field name="inspector_id"/>` بـ `<field name="inspector_ids" widget="many2many_tags"/>`.
   - استبدال `<field name="cashier_id"/>` بـ `<field name="cashier_ids" widget="many2many_tags"/>`.

4. **ملاحظة**: الإبقاء على `supervisor_id` كـ Many2one لأنه عادةً مسؤول واحد لكل مسار.

## 5. بيانات أولية لأنواع العدادات (Meter Type Data)

### 5.1 إثراء بيانات `utility.meter.type` بما يناسب السوق اليمني

**المشكلة:** البيانات الأولية الحالية في `utility_core/data/utility_data.xml` لأنواع العدادات محدودة جداً (4 أنواع فقط) ولا تمثل الواقع الفعلي في قطاع الكهرباء اليمني.

**التحليل:** السوق اليمني يضم عدة أنواع من العدادات المستخدمة فعلياً في مؤسسات الكهرباء (مثل مؤسسة الكهرباء اليمنية):

| النوع | الكود | الطور | الاستخدام |
|-------|-------|-------|-----------|
| عداد إلكتروميكانيكي (حثي) أحادي الطور | EM_SP | أحادي | الأكثر انتشاراً في المنازل القديمة |
| عداد إلكتروميكانيكي (حثي) ثلاثي الطور | EM_TP | ثلاثي | المنشآت الصغيرة والمتوسطة |
| عداد إلكتروني STS مسبق الدفع - أحادي | STS_SP_PRE | أحادي | المشتركين الجدد بنظام الدفع المسبق |
| عداد إلكتروني STS مسبق الدفع - ثلاثي | STS_TP_PRE | ثلاثي | المنشآت التجارية بنظام الدفع المسبق |
| عداد إلكتروني STS آجل الدفع - أحادي | STS_SP_POST | أحادي | العدادات الذكية أحادية الطور |
| عداد إلكتروني STS آجل الدفع - ثلاثي | STS_TP_POST | ثلاثي | العدادات الذكية ثلاثية الطور |
| عداد ذكي GSM/GPRS - أحادي | SMART_SP_GSM | أحادي | عدادات القراءة عن بُعد |
| عداد ذكي GSM/GPRS - ثلاثي | SMART_TP_GSM | ثلاثي | عدادات القراءة عن بُعد |
| عداد طاقة (كيلوواط ساعة) للربط | COUPLING_SP | أحادي | عدادات الربط للمحولات الصغيرة |
| عداد طاقة (كيلوواط ساعة) للربط - ثلاثي | COUPLING_TP | ثلاثي | عدادات الربط للمحولات والفيدرات |
| عداد معايرة (اختبار) | CHECK_METER | أحادي | للتحقق من دقة العدادات الأخرى |
| عداد تيار مستمر (DC) للطاقة الشمسية | DC_SOLAR | أحادي | نظم الطاقة الشمسية المرتبطة بالشبكة |

**الإجراء المطلوب:**
- تحديث `utility_core/data/utility_data.xml` بإضافة جميع الأنواع المذكورة أعلاه.
- إضافة `description` لكل نوع باللغة العربية لشرح استخدامه.
- إضافة معاملات (`noupdate="1"`) لمنع إعادة تعيين البيانات بعد التعديل اليدوي.
- إنشاء `data` file منفصل باسم `utility_meter_type_data.xml` إذا كبرت القائمة.

## 6. ربط موديل العداد بمنتج (Meter Model → Product)

### 6.1 إضافة `product_id` إلى `utility.meter.model`

**المشكلة:** موديل العداد (`utility.meter.model`) لا يرتبط بأي منتج (`product.product`)، مما يمنع:
- تتبع المخزون على مستوى الموديل.
- إنشاء حركات مخزنية عند تركيب/استبدال عداد من موديل معين.
- ربط التكلفة والسعر بالموديل عبر المنتج.
- استخدام `stock.lot` (سيريال نمبر) لكل عداد على حدة مع ربطه بالموديل.

**التحليل:** ربط `utility.meter.model` بـ `product.product` هو المفتاح لدمج العدادات مع نظام المخزون في Odoo. حاليًا `utility_inventory` يحاول ربط العدادات بالمنتجات بطريقة غير مستقرة (عبر `utility.meter.replacement`).

**الإجراء المطلوب:**
1. **إضافة حقل `product_id` في `utility.meter.model`**:
   ```python
   product_id = fields.Many2one(
       'product.product', 'المنتج',
       domain="[('type', '=', 'product'), ('detailed_type', '=', 'meter')]",
       help="المنتج الذي يمثل هذا الموديل في نظام المخزون والمحاسبة"
   )
   ```

2. **إضافة حقل `meter_model_id` في `product.product`** (عبر inherit):
   ```python
   class ProductProduct(models.Model):
       _inherit = 'product.product'
   
       meter_model_id = fields.Many2one(
           'utility.meter.model', 'موديل العداد',
           help="موديل العداد المرتبط بهذا المنتج"
       )
   ```
   - أو استخدام `is_meter = fields.Boolean('عداد كهرباء')` لتصنيف المنتج كعداد.

3. **تحديث واجهة `utility.meter.model`** (`utility_meter_model_views.xml`):
   - إضافة `product_id` في الفورم مع زر "فتح المنتج".
   - إظهار `product_id` في شجرة الموديلات.

4. **إنشاء فئة منتجات للعدادات** (اختياري):
- إضافة بيانات أولية لفئة منتجات `Meters / عدادات` في `product.category`.
- إضافة منتجات لكل موديل عداد معروف (من القائمة في 5.1).

## 7. تحسين قابلية تعديل الحقول في `utility.reading` حسب الحالة

### 7.1 مصفوفة صلاحية التعديل لكل حالة

**المشكلة:** الحماية الحالية في `write()` (السطور 87-97 في `utility_core/models/utility_reading.py`) تحمي فقط 7 حقول في حالة `billed`. لا توجد حماية للحالات الأخرى، مما يسمح بتعديل حقول حرجة مثل `meter_id` أو `reading_date` حتى بعد المراجعة أو الاعتماد.

**التحليل:** كل حالة في دورة حياة القراءة يجب أن تسمح بتعديل مجموعة محددة من الحقول فقط:

| الحقل | Draft | Under Review | Approved | Queued | Billed | Error |
|-------|-------|-------------|----------|--------|--------|-------|
| `meter_id` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `reading_date` | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `reading_value` | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `reading_category` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `reading_type` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `is_estimated` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `meter_image` | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `meter_image_secondary` | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `image_state` | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `review_notes` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `rejection_reason` | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| `remarks` | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `date_range_id` | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `reviewer_id` | — | — | — | — | — | — |
| `state` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**ملاحظات على المصفوفة:**
- `state` قابل للتعديل في جميع الحالات (عن طريق الأزرار `action_submit_review`, `action_approve`, `action_reject`).
- حقول المحسوبة (`consumption`, `previous_reading`, `consumption_alert`, إلخ) تتم إعادة حسابها تلقائياً ولا تُعدّل يدوياً.
- `meter_image` و `meter_image_secondary` يمكن إضافتها أثناء `under_review` لأن المراجع قد يطلب صوراً إضافية.
- في حالة `error`، يُسمح بتعديل `reading_value` و `reading_date` لإعادة المحاولة بعد تصحيح الخطأ.
- `meter_id` لا يمكن تغييره بعد الخروج من `draft` لأنه يغير هوية القراءة بالكامل.

**الإجراء المطلوب:**
1. **توسيع دالة `write()`** لتحقق من الحقول المسموحة حسب الحالة:
   ```python
   STATE_EDITABLE = {
       'draft': {'meter_id', 'reading_date', 'reading_value', 'reading_category',
                 'reading_type', 'is_estimated', 'meter_image', 'meter_image_secondary',
                 'image_state', 'rejection_reason', 'remarks', 'date_range_id',
                 'reading_source', 'active'},
       'under_review': {'meter_image', 'meter_image_secondary', 'image_state',
                        'review_notes', 'rejection_reason', 'state'},
       'approved': {'rejection_reason', 'state', 'active'},
       'queued': {'state'},
       'billed': {'active', 'remarks'},  # مع إمكانية bypass للتسويات
       'error': {'reading_date', 'reading_value', 'meter_image', 'meter_image_secondary',
                 'image_state', 'remarks', 'date_range_id', 'state'},
   }
   ```

2. **تحديث الواجهة** (`utility_reading_views.xml`) باستخدام `attrs` لجعل الحقول readonly:
   ```xml
   <field name="reading_value" attrs="{'readonly': [('state', 'not in', ('draft', 'error'))]}"/>
   <field name="meter_id" attrs="{'readonly': [('state', '!=', 'draft')]}"/>
   ...
   ```

3. **إبقاء `_bypass_reading_protection`** للسياقات الآمنة فقط (تسويات القراءات، API داخلي).

## 8. تقييد التعديل في `sale.order` حسب `bill_state`

### 8.1 منع التعديل عند الخروج من المسودة وإمكانية الرجوع إليها

**المشكلة:** نموذج `sale.order` (فاتورة الكهرباء) لا يملك حماية كافية ضد التعديل بعد تأكيد الفاتورة. حاليًا:
- `_calculate_amounts()` يسمح بإعادة الحساب في حالتي `draft` و `sent` (السطر 458).
- `action_draft()` يمنع الرجوع للمسودة فقط إذا كانت هناك فواتير محاسبية مرحلة (السطر 246-248).
- لا توجد حماية على مستوى `write()` لمنع تعديل الحقول الأساسية.

**التحليل:** دورة حياة `bill_state` هي:
```
draft → confirmed → sent → paid / overdue → cancelled
```
وكل انتقال لاحق يجب أن يقيّد التعديل:

| الحقل/الإجراء | Draft | Confirmed | Sent | Paid | Overdue | Cancelled |
|---------------|-------|-----------|------|------|---------|-----------|
| `customer_id` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `meter_id` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `reading_id` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `date_range_id` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `period_start` / `period_end` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `previous_reading` / `current_reading` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `consumption` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `order_line` (بنود الفاتورة) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `contract_template_id` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `amount_energy` / `amount_service` / ... | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `remarks` / `notes` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| الرجوع إلى `draft` | — | ✅ | ✅ | ❌ | ❌ | ❌ |

**الإجراء المطلوب:**
1. **إضافة override لدالة `write()`** في `utility.sale.order` تمنع تعديل الحقول المالية والفنية إذا لم تكن الحالة `draft`:
   ```python
   BILL_PROTECTED_FIELDS = {
       'customer_id', 'meter_id', 'reading_id', 'date_range_id',
       'period_start', 'period_end', 'previous_reading', 'current_reading',
       'consumption', 'contract_template_id', 'order_line',
       'amount_energy', 'amount_service', 'amount_discount',
       'amount_local_fee', 'amount_penalty',
   }
   
   def write(self, vals):
       for order in self:
           if order.bill_state != 'draft':
               changed = BILL_PROTECTED_FIELDS & set(vals)
               if changed:
                   raise ValidationError(
                       'لا يمكن تعديل الحقول المالية أو الفنية للفاتورة [%s] '
                       'لأن حالتها "%s". الرجاء إعادة الفاتورة إلى مسودة أولاً.'
                       % (order.name, order.bill_state)
                   )
       return super().write(vals)
   ```

2. **تحسين `action_draft()` للسماح بالرجوع إلى المسودة** بشرط عدم وجود فواتير محاسبية مرحلة:
   ```python
   def action_draft(self):
       for order in self:
           posted = order.invoice_ids.filtered(lambda i: i.state == 'posted')
           if posted:
               raise ValidationError(
                   'لا يمكن إعادة الفاتورة للمسودة، يوجد فواتير محاسبية مرحلة. '
                   'قم بإلغائها أولاً.')
           if order.bill_state in ('paid', 'cancelled'):
               raise ValidationError(
                   'لا يمكن إعادة فاتورة %s إلى المسودة.' % order.bill_state)
       return super().action_draft()
   ```

3. **تحديث الواجهة** (`utility_sale_order_views.xml`) باستخدام `attrs` أو `readonly` حسب `bill_state`:
   ```xml
   <field name="customer_id" attrs="{'readonly': [('bill_state', '!=', 'draft')]}"/>
   <field name="meter_id" attrs="{'readonly': [('bill_state', '!=', 'draft')]}"/>
   <field name="order_line" attrs="{'readonly': [('bill_state', '!=', 'draft')]}"/>
   ```

4. **فصل الأزرار حسب الحالة**:
   - زر "إعادة إلى مسودة" يظهر فقط في `confirmed` و `sent`.
   - زر "تأكيد" يظهر فقط في `draft`.
   - زر "إلغاء" يظهر في أي حالة غير `paid` أو `cancelled`.

## 9. تقرير طباعة الفاتورة (70mm × 290mm)

### 9.1 إعادة تصميم قالب التقرير لصفحة واحدة ضمن المقاس 70mm × 290mm

**المشكلة:** قالب التقرير الحالي (`utility_billing/views/utility_sale_order_report.xml`) يحتاج تحسينات في المحتوى فقط، التصميم الحالي مقارب للمطلوب ويحتاج:
1. **إزالة القيم الثابتة (Hardcoded)** واستبدالها كلها بمتغيرات من `sale.order`.
2. **استخدام `t-foreach` لجلب بنود الفاتورة** (`order_line`) بدلاً من الحقول الثابتة فقط.
3. **أبعاد الورق صحيحة** — لا تغيير.

**الإجراء المطلوب:**
1. **الحفاظ على أبعاد الورق الحالية** (لا تغيير):
   ```xml
   <record id="paperformat_utility_receipt" model="report.paperformat">
       <field name="page_width">290</field>
       <field name="page_height">70</field>
       <field name="orientation">Portrait</field>
       <field name="dpi">90</field>
       <!-- باقي الإعدادات كما هي -->
   </record>
   ```

2. **الحفاظ على التصميم الحالي** (3 أعمدة في الرأس، جدول الاستهلاك، footer) مع إزالة الثوابت فقط.

3. **ضمان احتواء كل البيانات في صفحة واحدة** بارتفاع 70mm:
   - استخدام خط أصغر (6pt–7pt) للعناصر غير الرئيسية.
   - تقليل الهوامش الداخلية (padding) إلى 1mm–2mm.
   - دمج بنود الفاتورة (`order_line`) في جدول مضغوط بدلاً ازدياد طول القالب.
   - تصغير QR code إلى أبعاد 12mm × 12mm.
   - إزالة `min-height: 64mm` واستبداله بـ `height: 100%` أو `page-break-inside: avoid` فقط.

4. **إزالة الثوابت (Hardcoded values)** — استبدال كل default/String ثابت بمتغير حقيقي:
   ```xml
   <div>الاسم: <span t-esc="o.partner_id.name"/></div>
   <!-- بدلاً من: <span t-esc="o.partner_id.name or 'الاسم غير متوفر'"/> -->
   ```
   أو إبقاء fallback ولكن بقيمة منطقية (مثل `--`).

5. **استخدام `t-foreach` لجلب بنود الفاتورة** (`order_line`) بدلاً من الحقول الثابتة:
   ```xml
   <t t-foreach="o.order_line" t-as="line">
       <tr>
           <td style="padding: 0.5mm 1mm; font-size: 6pt;"><span t-esc="line.name"/></td>
           <td style="padding: 0.5mm 1mm; font-size: 6pt;"><span t-esc="line.price_subtotal" t-options="{'widget': 'monetary', 'display_currency': o.currency_id}"/></td>
       </tr>
   </t>
   ```

## 10. تعيين المنتج والحساب المحاسبي المناسب لكل بند في `account.move`

### 10.1 إسناد `product_id` و `account_id` حسب نوع البند (`meter_line_type`)

**المشكلة:** دالة `_prepare_invoice_line()` في `utility.sale.order.line` (السطور 793-808 في `utility_sale_order.py`) لا تعيّن المنتج والحساب المناسبين لجميع أنواع بنود الفاتورة. حالياً:
- فقط `discount` و `penalty` يحصلان على `account_id` مخصص.
- باقي الأنواع (`consumption`, `service_charge`, `fixed_fee`, `local_fee`) تعتمد على المنتج الافتراضي وحسابه.
- لا يوجد `product_id` مخصص لكل نوع بند على حدة.

**التحليل:** لكل نوع بند (محدد في `meter_line_type`) يجب تعيين **منتجه المستقل** و **حسابه المحاسبي المناسب**:
1. **المنتج المناسب** (`product_id`) — لضمان صحة التقارير المالية والمخزنية.
2. **الحساب المحاسبي المناسب** (`account_id`) — لضمان صحة القيود المحاسبية.
3. **مصادر المنتج والحساب** حسب الأولوية:
   - من بنود قالب العقد (`contract.template.line`) مباشرة.
   - من إعدادات الشركة (`res.company`) لكل منتج على حدة.
   - من فئة المشترك (`utility.subscriber`) لحساب الإيراد.
   - من المنتج نفسه (`product.product.property_account_income_id`) كحل أخير.

| `meter_line_type` | المنتج المستقل (`product_id`) | الحساب المقترح (`account_id`) |
|-------------------|-----------------------------|------------------------------|
| `consumption` | منتج الطاقة (kWh) | `subscriber.revenue_account_id` أو افتراضي |
| `service_charge` | منتج رسم الخدمة | من المنتج أو الإعدادات |
| `fixed_fee` | منتج الرسم الثابت | من المنتج أو الإعدادات |
| `mu_allim` | `company.mu_allim_product_id` | من المنتج |
| `cleaning` | `company.cleaning_product_id` | من المنتج |
| `municipality` | `company.local_fee_product_id` | من المنتج |
| `discount` | منتج الخصم | `company.discount_account_id` |
| `penalty` | `company.penalty_product_id` | `company.fine_account_id` |
| `other` | المنتج الافتراضي | حسب `fiscal_position_id` |

**الإجراء المطلوب:**

1. **توسيع دالة `_prepare_invoice_line()`** في `UtilitySaleOrderLine` لتعيين المنتج والحساب لجميع الأنواع:
   ```python
   def _prepare_invoice_line(self, **optional_values):
       res = super()._prepare_invoice_line(**optional_values)

       if self.sponsor_id:
           res['partner_id'] = self.sponsor_id.id

       account_id = False
       product_id = False
       company = self.company_id or self.env.company

       if self.meter_line_type == 'consumption':
           if self.order_id.customer_id:
               subscriber = self.order_id.customer_id.subscriber_id
               if subscriber and subscriber.revenue_account_id:
                   account_id = subscriber.revenue_account_id.id

       elif self.meter_line_type == 'mu_allim' and company.mu_allim_product_id:
           product_id = company.mu_allim_product_id.id
      elif self.meter_line_type == 'cleaning' and company.cleaning_product_id:
           product_id = company.cleaning_product_id.id
      elif self.meter_line_type == 'municipality' and company.local_fee_product_id:
           product_id = company.local_fee_product_id.id

       elif self.meter_line_type == 'discount':
           account_id = company.discount_account_id.id if company.discount_account_id else account_id

       elif self.meter_line_type == 'penalty':
           if company.penalty_product_id:
               product_id = company.penalty_product_id.id
           account_id = company.fine_account_id.id if company.fine_account_id else account_id

       if not product_id and self.product_id:
           product_id = self.product_id.id
       if product_id:
           res['product_id'] = product_id
       if account_id:
           res['account_id'] = account_id

       return res
   ```

2. **إضافة قيم جديدة إلى `meter_line_type`** في `sale.order.line` لتحل محل `local_fee`:
   ```python
   meter_line_type = fields.Selection([
       ('consumption', 'استهلاك'),
       ('service_charge', 'رسم خدمة ثابت'),
       ('fixed_fee', 'رسم ثابت (قديم)'),
       ('mu_allim', 'رسم المعلم'),         # ← جديد
       ('cleaning', 'رسم النظافة'),         # ← جديد
       ('municipality', 'رسم المجلس المحلي'), # ← جديد
       ('discount', 'خصم'),
       ('penalty', 'غرامة'),
       ('other', 'أخرى'),
   ], string='نوع البند')
   ```

3. **تحديث `contract.template.line`** لاستخدام القيم الجديدة بدلاً من `local_fee` + `local_fee_kind`:
   - إزالة حقل `local_fee_kind` من `contract.template.line`.
   - جعل `meter_line_type` في قالب العقد يتضمن `mu_allim`, `cleaning`, `municipality` كخيارات منفصلة.
   - تعديل `_accumulate_amount()` في `sale.order` لإضافة حالات `mu_allim`, `cleaning`, `municipality`.

4. **إضافة منتجات افتراضية لكل `meter_line_type`** ضمن بيانات أولية (`data/`) حتى لا تفشل الفوترة عند عدم وجود إعدادات:
   - منتج استهلاك (kWh)
   - منتج رسم الخدمة
   - منتج المعلم
   - منتج النظافة
   - منتج المجالس المحلية
   - منتج الغرامات
   - منتج الخصم

## 11. توحيد والتحقق من أرقام الهواتف (9 أرقام بدون مفتاح دولة)

### 11.1 فرض 9 أرقام لجميع حقول الهاتف والجوال في Utility

**المشكلة:** لا يوجد أي تحقق (validation) على أرقام الهواتف في جميع موديولات Utility. البيانات الأولية تحتوي على صيغ مختلفة:
- `+967-77-1122334` (بمفتاح الدولة)
- `+966 55 123 4567` (بمفتاح دولة آخر)
- `+967-77-xxxxxxx` في الـ Placeholder (wizard)
- لا قيود على الطول أو الصيغة

**التحليل:** في اليمن، أرقام الجوال والهاتف الثابت هي 9 أرقام بدون مفتاح الدولة. يجب فرض:
- رقم واحد متصل من 9 أرقام (بدون فواصل أو شرطات).
- رفض أي رقم يبدأ بـ `+` أو `00`.
- رفض أي رقم يزيد عن 9 أرقام أو يقل عن 9 أرقام.
- الاستثناء: أرقام خدمة الجمهور القصيرة (مثل `8000144`) — لكن هذا خارج نطاق Field Validation العادي.

**الحقول المستهدفة:**

| الموديل | الحقل | الملف | السطر | النوع |
|---------|-------|-------|-------|-------|
| `res.partner` (Odoo std) | `phone` | `utility_core/models/utility_res_partner.py` | — | `Char` موروث |
| `res.partner` (Odoo std) | `mobile` | `utility_core/models/utility_res_partner.py` | — | `Char` موروث |
| `utility.customer` | `phone` | `utility_customer.py` | 26 | Related (`partner_id.phone`) |
| `utility.customer` | `mobile` | `utility_customer.py` | 27 | Related (`partner_id.mobile`) |
| `utility.office` | `phone` | `utility_office.py` | 15 | `Char` مباشر |
| `utility.staff` | `phone` | `utility_staff.py` | 16 | `Char` مباشر |
| `utility.staff` | `mobile` | `utility_staff.py` | 17 | `Char` مباشر |
| `utility.notification.log` | `mobile` | `utility_notification.py` | 24 | `Char` مباشر |
| `utility.customer.wizard` | `mobile` | `utility_customer_wizard.py` | 10 | `Char` (مطلوب) |
| `utility.customer.wizard` | `phone` | `utility_customer_wizard.py` | 11 | `Char` |

**الإجراء المطلوب:**

1. **إنشاء دالة تحقق عامة** يمكن إعادة استخدامها عبر الموديولات:
   ```python
   from odoo.exceptions import ValidationError
   import re
   
   PHONE_9_RE = re.compile(r'^\d{9}$')
   
   def validate_phone_9(value, field_label='رقم الهاتف'):
       """التحقق من أن الرقم يتكون من 9 أرقام فقط بدون مفتاح دولة."""
       if not value:
           return  # السماح بالقيم الفارغة
       if not PHONE_9_RE.match(value):
           raise ValidationError(
               '%s يجب أن يتكون من 9 أرقام فقط، بدون مفتاح دولة (+967/00).'
               % field_label
           )
   ```

2. **إضافة `@api.constrains` على `res.partner`** للتحقق من `phone` و `mobile`:
   ```python
   class ResPartner(models.Model):
       _inherit = 'res.partner'
   
       @api.constrains('phone', 'mobile')
       def _check_phone_9_digits(self):
           for partner in self:
               validate_phone_9(partner.phone, 'رقم الهاتف')
               validate_phone_9(partner.mobile, 'رقم الجوال')
   ```
   هذا يكفي للتحقق من `utility.customer.phone` و `utility.customer.mobile` لأنهما حقول Related.

3. **إضافة `@api.constrains` على `utility.office`**:
   ```python
   class UtilityOffice(models.Model):
       _inherit = 'utility.office'
   
       @api.constrains('phone')
       def _check_phone_9_digits(self):
           for rec in self:
               validate_phone_9(rec.phone, 'رقم الهاتف')
   ```

4. **إضافة `@api.constrains` على `utility.staff`**:
   ```python
   class UtilityStaff(models.Model):
       _inherit = 'utility.staff'
   
       @api.constrains('phone', 'mobile')
       def _check_phone_9_digits(self):
           for rec in self:
               validate_phone_9(rec.phone, 'رقم الهاتف')
               validate_phone_9(rec.mobile, 'رقم الجوال')
   ```

5. **إضافة `@api.constrains` على `utility.notification.log`**:
   ```python
   class UtilityNotificationLog(models.Model):
       _inherit = 'utility.notification.log'
   
       @api.constrains('mobile')
       def _check_phone_9_digits(self):
           for rec in self:
               validate_phone_9(rec.mobile, 'رقم الجوال')
   ```

6. **إضافة تحقق في `utility.customer.wizard`**:
   ```python
   class UtilityCustomerWizard(models.TransientModel):
       _inherit = 'utility.customer.wizard'
   
       @api.constrains('mobile', 'phone')
       def _check_phone_9_digits(self):
           for rec in self:
               validate_phone_9(rec.mobile, 'رقم الجوال')
               validate_phone_9(rec.phone, 'رقم الهاتف')
   ```

7. **وضع الدالة العامة** في ملف مشترك مثل `utility_core/models/utility_validation.py` أو داخل `utility_core/__init__.py` لاستيرادها بسهولة.

8. **تحديث البيانات الأولية** (`utility_core/data/utility_sample_data.xml`, `utility_prepaid/data/utility_demo.xml`) لإزالة المفاتيح الدولية والشرطات من الأرقام.

9. **تحديث الـ Placeholder** في `utility_customer_wizard_views.xml` من `+967-77-xxxxxxx` إلى `777xxxxxx`.
