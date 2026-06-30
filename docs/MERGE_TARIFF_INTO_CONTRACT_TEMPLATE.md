# خطة دمج `utility.tariff` وملحقاتها داخل `utility.contract.template`

> **[تم الإنجاز بالكامل ✔️]** تم الانتهاء من تنفيذ هذه الخطة بنجاح وإلغاء نظام التعرفة المنفصل بالكامل ودمجه في قوالب العقود.

> **الهدف:** إلغاء النماذج المستقلة للتعرفة (`utility.tariff`, `utility.tariff.block`, `utility.tariff.history`, `utility.tariff.category`) وجعلها جزءاً عضوياً من `utility.contract.template` و`utility.contract.template.line`، حتى يصبح **قالب العقد هو المصدر الوحيد للحقيقة** للتسعير، بينما يبقى `utility.customer` مالكاً لقالب واحد فقط بدون حاجة لاختيار تعرفة منفصلة.

---

## 1) الوضع الحالي (Baseline)

| النموذج | الدور الحالي | المشكلة |
|---|---|---|
| `utility.tariff` | كيان مستقل (اسم/كود/نوع/سعر kWh/رسم ثابت/...) | ازدواجية: نفس البيانات تُحفظ في التعرفة **وفي** بنود القالب. |
| `utility.tariff.block` | One2many من التعرفة (`block_ids`) | منطق التسعير التدريجي معزول عن قالب العقد. |
| `utility.tariff.history` | سجل تغييرات أسعار التعرفة | لا يرتبط بقراءة/فاتورة، فقط بالتعرفة المجردة. |
| `utility.tariff.category` | تصنيف عام للتعرفة (سكني/تجاري/...) | تصنيف منفصل عن `utility.subscriber` رغم تشابه المفهوم. |
| `utility.contract.template` | قالب العقد، يحوي `tariff_id` (M2O) + `line_ids` (O2M) | إشارة مرجعية لتعرفة مستقلة → نقطتا إدارة بدلاً من واحدة. |
| `utility.contract.template.line` | بند واحد برسم/استهلاك/خدمة، مع `meter_line_type` و`qty_formula_id` | يحتوي بالفعل جزءاً كبيراً من منطق التسعير، لكنه يعتمد على التعرفة لجلب السعر. |

**الاستدعاءات الخارجية الحالية التي يجب إصلاحها:**

- `utility_customer.py:64` → `tariff_id` (M2O) + `tariff_segment_id` (related) + `_compute_tariff_blocks` (`:106`) + onchange `_onchange_subscriber_tariff` (`:170`).
- `utility_res_partner.py:72` → ربط بقالب العقد فقط (لا يذكر التعرفة).
- `utility_subscriber.py:24-25` → `default_tariff_id` + `default_contract_template_id`.
- `utility_customer_wizard.py:28,73` → `tariff_id` كحقل مطلوب، مع بحث عن تعرفة مطابقة.
- `utility_recurring_invoice.py:5-82` → `_prepare_sale_order_data` يستهلك `account.tariff_id` و`tariff.price_per_kwh`.
- `utility_sale_order.py:30,320` → `tariff_id` على `sale.order`.
- `utility_pos_order.py:10` → `tariff_id` على `pos.order` (مسبق الدفع).
- `utility_token.py:24` → `tariff_id` على الـtoken.
- `utility_formula.py:20` → المتغير `tariff` يُمرَّر للمعادلات.

**عدد الأسطر/الملفات المتأثرة ≈ 12 ملف Python + 6 ملفات XML + سطور في `ir.model.access.csv`.**

---

## 2) الرؤية المستهدفة (Target State)

```
utility.contract.template  (1)
   ├── name / code
   ├── subscriber_ids           (M2M utility.subscriber)
   ├── recurring_rule_type / interval / invoicing_type
   ├── pricing_mode: flat | block | seasonal | tou | tier
   ├── price_per_kwh            (الافتراضي، يُورَث للبنود)
   ├── fixed_charge / service_charge
   ├── min_charge / max_charge
   ├── effective_date / end_date  → is_active
   ├── block_ids                (O2M utility.contract.template.block)  ← was utility.tariff.block
   ├── history_ids              (O2M utility.contract.template.history) ← was utility.tariff.history
   └── line_ids                 (O2M utility.contract.template.line)  ← مع توسع price_type
```

**نماذج سيتم حذفها:** `utility.tariff`, `utility.tariff.block`, `utility.tariff.history`, `utility.tariff.category`.

**نماذج جديدة:**
- `utility.contract.template.block` (بدلاً من `utility.tariff.block`، FK → `template_id`).
- `utility.contract.template.history` (بدلاً من `utility.tariff.history`، FK → `template_id` + `sale_order_id` لربط السجل بفاتورة).

**فئات المشتركين:** تُحذَف `utility.tariff.category` ويُستخدم `utility.subscriber.category_id` (إن وُجد) أو يُضاف حقل `category` جديد على `utility.subscriber`. **القرار النهائي: نقل الحقل إلى `utility.subscriber`** لتفادي ازدواجية التصنيف.

---

## 3) مراحل التنفيذ

### المرحلة 0 — تجهيز فرع git
1. إنشاء فرع: `git checkout -b refactor/merge-tariff-into-contract-template`.
2. نسخ احتياطي لقاعدة البيانات وأخذ dump لـ XML IDs الحالية للتعرفة (سيُحتاج لسكريبت الترحيل).

### المرحلة 1 — إضافة النماذج الجديدة (Backward-Compatible)
> في هذه المرحلة **لا نحذف** أي نموذج قديم، نضيف فقط النماذج الجديدة ونجعل القديمة `_inherit` لها حتى يبقى الـ API الخارجي يعمل.

1. إنشاء `utility_contract_template.py` بديل يحوي:
   - جميع حقول `utility.tariff` الحالية (`pricing_mode`, `price_per_kwh`, `fixed_charge`, `service_charge`, `min_charge`, `max_charge`, `effective_date`, `end_date`, `is_active`، إلخ). مع **حذف** `tax_percentage` و`fuel_adjustment` (انظر 8.7).
   - حقل `subscriber_ids` (موجود أصلاً، يُثبَّت).
2. إنشاء `utility_contract_template_block.py` كنموذج جديد (نسخة طبق الأصل من `utility.tariff.block` لكن بـ M2O على `utility.contract.template`).
3. إنشاء `utility_contract_template_history.py` كنموذج جديد.
4. كتابة `__init__.py` (إضافة الثلاثة).
5. تحديث `__manifest__.py`: إضافة الملفات الثلاثة الجديدة في `data` (سيتم في مرحلة لاحقة قبل الحذف النهائي).

### المرحلة 2 — سكريبت ترحيل البيانات (Migration Script)
إنشاء `utility_core/migrations/16.0.2.0.0/` يحوي:
- `pre-migrate.py`: نسخ بيانات `utility.tariff` → قالب عقد جديد (إن لم يوجد)، نسخ `block_ids` → `utility.contract.template.block`، نسخ `history_ids` → `utility.contract.template.history`.
- `post-migrate.py`:
  - ربط `utility.customer.tariff_id` → `contract_template_id.tariff_template_id` (عمود مؤقت).
  - ربط `account.payment`/`pos.order`/`utility.token`/`sale.order.tariff_id` → `template_id` عبر عمود مساعد جديد `legacy_tariff_id` (Many2one للقراءة فقط).
  - ضبط `ir.model.data` لإبقاء الـ XML IDs القديمة تعمل كـ aliases للنماذج الجديدة.

### المرحلة 3 — جعل القديم يرث الجديد (Compat Layer)
1. تعديل `utility_tariff.py` ليصبح:
   ```python
   class UtilityTariff(models.Model):
       _name = 'utility.tariff'
       _auto = False   # جدول في DB يصبح alias
       _inherit = 'utility.contract.template'
   ```
   + إضافة `view` يُخفي نموذج `utility.tariff` من القوائم ويحوّل الـ form إلى `utility.contract.template`.
2. تعديل `utility_tariff_block.py` (المستقل حالياً) → `_inherit = 'utility.contract.template.block'` واسم فني alias.
3. تعديل `utility_tariff_history.py` → نفس الفكرة.
4. تعديل `utility_tariff_category.py` → `_inherit = 'utility.subscriber'` (alias على `category`).
5. إضافة حقول مساعدة `Many2one` بنمط `legacy_id` للربط بأثر رجعي (للتقارير فقط).

### المرحلة 4 — تحديث المستهلكين
| الملف | التعديل |
|---|---|
| `utility_customer.py` | حذف `tariff_id`, `tariff_segment_id`, `_compute_tariff_blocks`. استبدال `tariff_id` بـ `contract_template_id` (مطلوب). تعديل `_onchange_subscriber_tariff` → `_onchange_subscriber_template` يبحث عن قالب مناسب بناءً على `subscriber_id` فقط. |
| `utility_subscriber.py` | حذف `default_tariff_id`. الإبقاء على `default_contract_template_id`. (يمكن إضافة `category_id` بدلاً من `default_tariff_id` إن لزم). |
| `utility_customer_wizard.py` | حذف `tariff_id`. استبداله بـ `contract_template_id`. |
| `utility_recurring_invoice.py` | تعديل `_prepare_sale_order_data`: استخدام `account.contract_template_id` بدل `account.tariff_id`. استبدال `tariff.price_per_kwh` بـ `template.price_per_kwh` و`tariff.fixed_charge` بـ `template.fixed_charge`. |
| `utility_sale_order.py` | حذف `tariff_id`. استبداله بـ `contract_template_id` (Many2one) أو دالة `compute` تجلبه من `customer_id.contract_template_id`. |
| `utility_pos_order.py` | نفس ما سبق: حذف `tariff_id`، استخدام `contract_template_id` (أو دالة `_get_pricing_template()`). |
| `utility_token.py` | حذف `tariff_id`، استخدام `pos_order_id.contract_template_id`. |
| `utility_formula.py` | تحديث تعليق/مساعدة: المتغير `tariff` → `template` (مع إبقاء `tariff` كـ alias للحقول الأساسية للتوافق). |

### المرحلة 5 — تحديث الواجهات
1. **`utility_contract_template_views.xml`**:
   - إعادة هيكلة الـform إلى Notebook:
      - تبويب **التسعير**: `pricing_mode`, `price_per_kwh`, `fixed_charge`, `service_charge`, `min_charge`, `max_charge`, `effective_date`, `end_date`.
     - تبويب **الشرائح التدريجية** (يظهر فقط حين `pricing_mode in ('block','tier','seasonal','tou')`): `block_ids`.
     - تبويب **سجل التغييرات**: `history_ids` (للقراءة فقط).
     - تبويب **بنود العقد** (موجود): `line_ids` مع تعزيز دوره.
2. **`utility_tariff_views.xml`**: استبداله بقالب بسيط `<menuitem>` يحوّل إلى `action_utility_contract_template` مع `default_pricing_mode='flat'`، أو إخفاء القائمة تماماً. **القرار النهائي: إخفاء القائمة + إعادة تسمية "قوالب العقود" إلى "قوالب العقود والتسعير"**.
3. **`utility_tariff_block_views.xml`**، **`utility_tariff_history_views.xml`**، **`utility_tariff_category_views.xml`**: حذفها (أو إفراغها لتفادي خطأ `ir.model.data`).
4. **`utility_customer_views.xml`**: حذف حقل `tariff_id` من الـ tree/form، استبداله بـ `contract_template_id` (إن لم يكن ظاهراً).

### المرحلة 6 — الأمان والـ CSV
1. `utility_core/security/ir.model.access.csv`:
   - حذف سطور `access_utility_tariff_*`, `access_utility_tariff_block_*`, `access_utility_tariff_history_*`, `access_utility_tariff_category_*`.
   - إضافة سطور للنماذج الجديدة: `utility.contract.template.block`, `utility.contract.template.history`.
2. `utility_core/security/utility_security.xml`: لا تغيير (المجموعات موجودة وتخدم `utility.contract.template`).

### المرحلة 7 — تحديث التقارير
- `utility_receipt_report.xml` (وأي قالب طباعة): استبدال `o.tariff_id.name` بـ `o.contract_template_id.name`.
- `transformer_balance_report.xml`: التحقق من استخدام التعرفة (لا أظن يستخدمها).

### المرحلة 8 — اختبارات وفحص
- تشغيل Odoo بـ `-u utility_core` على قاعدة بيانات نسخة (مرتين: مرة على النسخة القديمة لمرحلة الترحيل، ومرة على قاعدة جديدة نظيفة).
- فتح شاشات:
  1. `قوالب العقود` (الجديدة): إنشاء قالب سكني بسعر kWh، إضافة شريحتين، إضافة بند استهلاك.
  2. `المشتركين`: التأكد أن `_onchange_subscriber_template` يختار قالباً صحيحاً.
  3. `POS Prepaid`: بيع طاقة وتوليد token — يجب أن يستخدم `pos_order.contract_template_id.price_per_kwh`.
  4. `Recurring Invoice`: إصدار فاتورة دورية لقالب جديد.
- التحقق من:
  - اختفاء `Tariffs` و`Tariff Blocks` و`Tariff History` و`Tariff Categories` من القوائم.
  - التقارير تُظهر اسم القالب بدل اسم التعرفة.
  - `action_sync_with_tariff` السابق → يُعاد تسميته إلى `action_sync_pricing` ويعمل على حقول القالب نفسه (إزالة الاستدعاء الذاتي للتعرفة).

### المرحلة 9 — تنظيف نهائي
1. حذف `utility_tariff.py` (بعد التأكد أن لا مستهلك خارجي).
2. حذف `utility_tariff_block.py` و`utility_tariff_history.py` و`utility_tariff_category.py` (نقل الـ `_inherit` للاسم الجديد أولاً).
3. حذف XMLs الأربعة الخاصة بالتعرفة.
4. تحديث `__init__.py` لإزالة `utility_tariff`.
5. تحديث `__manifest__.py` لحذف الإدخالات.
6. تحديث `EXECUTION_PLAN.md` و`GAP_ANALYSIS_PLAN.md` و`AGENTS.md` ليعكس الواقع الجديد.

### المرحلة 10 — التواصل والتوثيق
- كتابة `CHANGELOG.md` يوضح للمستخدمين:
  - أين تذهب أسعار التعرفة الآن (داخل القالب).
  - كيف يُستورد قالب تسعير من Excel/CSV (الاستيراد العادي لـ `utility.contract.template`).
  - اسم الزر الجديد: «مزامنة البنود مع التسعير» بدل «مزامنة البنود مع التعرفة».
- إخطار فريق الفوترة/العمليات لأن الـmenu اختفى.

---

## 4) خريطة الترحيل الميداني (Data Mapping)

| الحقل القديم | الجدول/النموذج القديم | الحقل الجديد | الجدول/النموذج الجديد |
|---|---|---|---|
| `name` | `utility.tariff` | `name` | `utility.contract.template` |
| `code` | `utility.tariff` | `code` | `utility.contract.template` |
| `category_id` | `utility.tariff` | `category_id` (جديد على `utility.subscriber` أو يُحذف) | `utility.subscriber` |
| `subscriber_ids` | `utility.tariff` | `subscriber_ids` | `utility.contract.template` |
| `tariff_type` | `utility.tariff` | `pricing_mode` | `utility.contract.template` |
| `price_per_kwh` | `utility.tariff` | `price_per_kwh` | `utility.contract.template` |
| `fixed_charge` | `utility.tariff` | `fixed_charge` | `utility.contract.template` |
| `service_charge` | `utility.tariff` | `service_charge` | `utility.contract.template` |
| `tax_percentage` | `utility.tariff` | _(محذوف)_ | — |
| `fuel_adjustment` | `utility.tariff` | _(محذوف)_ | — |
| `effective_date` | `utility.tariff` | `effective_date` | `utility.contract.template` |
| `end_date` | `utility.tariff` | `end_date` | `utility.contract.template` |
| `is_active` | `utility.tariff` | `is_active` (compute) | `utility.contract.template` |
| `block_ids.*` | `utility.tariff.block` | `block_ids.*` | `utility.contract.template.block` |
| `history_ids.*` | `utility.tariff.history` | `history_ids.*` | `utility.contract.template.history` |
| `tariff_id` (FK من customer) | `utility.customer` | `contract_template_id` | `utility.customer` |

---

## 5) المخاطر والتخفيف

| المخاطرة | الاحتمال | الأثر | التخفيف |
|---|---|---|---|
| كسر تقارير/تقارير مخصصة تشير لـ `utility.tariff` | متوسط | عالٍ | مرحلة Compat Layer + بحث grep قبل الحذف. |
| فشل ترحيل بيانات الإنتاج | منخفض | عالٍ | اختبار الترحيل على staging + نسخ احتياطي DB. |
| كسر تكاملات خارجية (REST API) | متوسط | متوسط | إبقاء XML IDs القديمة تعمل كـ aliases في `ir.model.data` (مرحلة 2). |
| ارتباك المستخدم بسبب انتقال التسعير للقالب | عالٍ | منخفض | إشعار مسبق + تسمية القائمة الجديدة + tooltip في الـform. |
| تأثر أداء الحساب (`calculate_kwh` على التعرفة) | منخفض | منخفض | نقل المنطق إلى `utility.contract.template` (دالة بنفس الاسم) مع cache. |

---

## 6) معايير القبول (Definition of Done)

- [x] لا يبقى أي نموذج اسمه `utility.tariff*` في `utility_core` (أو فقط `_auto=False` alias).
- [x] كل قيمة تسعير (`price_per_kwh`, `block_ids`, ...) محفوظة على `utility.contract.template` أو نماذجه الفرعية.
- [x] `utility.customer` يحوي `contract_template_id` فقط (لا `tariff_id`).
- [x] زر «مزامنة التسعير» يعمل على قالب العقد بدون الإشارة لنموذج خارجي.
- [x] POS Prepaid وBilling وRecurring Invoices تعمل بدون تعديل سلوكي (نفس المبالغ الصادرة).
- [x] اختبارات يدوية لـ 5 سيناريوهات (سكني، تجاري، صناعي، TOU، مع إعانات).
- [x] `ir.model.access.csv` و`utility_security.xml` متسقان.
- [x] `__manifest__.py` و`AGENTS.md` محدّثان.

---

## 7) تقدير الجهد (Story Points تقديرية)

| المرحلة | النقاط |
|---|---|
| 0: تحضير فرع | 0.5 |
| 1: نماذج جديدة | 3 |
| 2: سكريبت ترحيل | 5 |
| 3: Compat Layer | 5 |
| 4: تحديث المستهلكين | 5 |
| 5: تحديث الواجهات | 3 |
| 6: الأمان | 1 |
| 7: التقارير | 2 |
| 8: اختبارات | 3 |
| 9: تنظيف نهائي | 2 |
| 10: توثيق | 1 |
| **المجموع** | **30.5 SP** |

> تعادل تقريباً **3–4 أسابيع** لمطوّر واحد بدوام كامل، أو **1.5 أسبوع** لفردين (أحدهما للهجرة، والآخر للمستهلكين والواجهات).

---

## 8) أنماط التسعير الخمسة (`pricing_mode`)

> كان يُعرف سابقاً بـ `tariff_type` في `utility.tariff`، ويُنقل كحقل `pricing_mode` على `utility.contract.template`. اختيار النمط يحدد **كيف يُحسب المبلغ النهائي** من `consumption` (الاستهلاك بالـ kWh) ومكونات التسعير الأخرى.

### 8.1) `flat` — سعر موحّد
**الفكرة:** كل kWh يُسعَّر بسعر واحد ثابت بغض النظر عن الكمية أو الوقت.

**الحقول المستخدمة:**
- `price_per_kwh` (إلزامي)
- `fixed_charge`, `service_charge` (اختيارية)

**صيغة الحساب:**
```
energy_charge = consumption × price_per_kwh
fixed_charge  = fixed_charge              # مبلغ ثابت لا يتأثر بالاستهلاك
service_charge= service_charge
total         = energy_charge + fixed_charge + service_charge
```

> **ملاحظة:** الضريبة تُضاف لاحقاً عبر `account.tax` على بنود أمر البيع (وليس على القالب).

**مثال:** عقد سكني بسيط: `price_per_kwh = 0.20`، `fixed_charge = 5`، استهلاك 200 kWh.
```
energy = 200 × 0.20 = 40
total  = 40 + 5 = 45
```

**متى يُستخدم:** العقود السكنية الصغيرة، الحسابات ذات الشريحة الواحدة.

---

### 8.2) `block` — شرائح/تدريج (Block Tariff)
**الفكرة:** سعر kWh يتغير حسب **كمية الاستهلاك نفسها** (شرائح تصاعدية أو تنازلية).

**الحقول المستخدمة:**
- `block_ids` (One2many على `utility.contract.template.block`) — كل شريحة تحوي:
  - `from_kwh`, `to_kwh` (المدى؛ `to_kwh=0` تعني "مفتوحة").
  - `price_per_kwh` (سعر هذه الشريحة).

**صيغة الحساب (تدريج تصاعدي نموذجي):**
```
energy_charge = Σ (kWh_in_block_i × block_i.price_per_kwh)
                for i in blocks sorted by sequence
                kWh_in_block = min(consumption, block.to_kwh) - block.from_kwh
```
- إذا `consumption` ضمن الشريحة i: ادفع سعر الشريحة i.
- إذا تجاوز الشريحة: ادفع سعر الشريحة i عن الجزء ضمنها، ثم انتقل للشريحة i+1 وهكذا.

**مثال:** 3 شرائح:
| الشريحة | من kWh | إلى kWh | السعر/kWh |
|---|---|---|---|
| 1 | 0 | 100 | 0.15 |
| 2 | 100 | 300 | 0.25 |
| 3 | 300 | ∞ | 0.40 |

استهلاك 350 kWh:
```
0–100  → 100 × 0.15 = 15
100–300 → 200 × 0.25 = 50
300–350 → 50  × 0.40 = 20
energy_charge = 85
```

**الشرائح التنازلية (Inverted Blocks):** نفس المنطق لكن سعر الشريحة الأولى أعلى من الثانية. شائع في دعم الفئات الأكثر استهلاكاً.

**متى يُستخدم:** أغلب الشرائح السكنية والتجارية الصغيرة، حساب الاستهلاك المنزلي الحقيقي.

---

### 8.3) `tier` — مستويات (Tier Tariff)
**الفكرة:** نسخة "إجمالي" من الـ block، حيث **كل kWh** يُسعَّر بسعر **الشريحة الأخيرة التي وصل إليها الاستهلاك**، وليس بسعر كل شريحة على حدة (Tier vs Block).

**الفرق الجوهري عن `block`:**

| الوضع | block (تدريج) | tier (مستوى) |
|---|---|---|
| استهلاك 250 kWh ضمن 3 شرائح أعلاه | 15 + 37.5 = 52.5 | 250 × 0.25 = 62.5 |
| المنطق | كل شريحة بسعرها | شريحة واحدة بسعرها لكل الاستهلاك |

**صيغة الحساب:**
```
tier = max(block where consumption >= block.from_kwh)
unit_price = tier.price_per_kwh
energy_charge = consumption × unit_price
```

**متى يُستخدم:** شرائح دافعي الضرائب، تسعير الخدمات الرقمية، حيث يُصنَّف العميل في مستوى واحد بناءً على إجمالي استهلاكه.

---

### 8.4) `seasonal` — موسمي
**الفكرة:** نفس منطق `block` (شرائح تدريجية)، لكن **كل شريحة محصورة بنطاق شهري** (لا تتطبق إلا في أشهر معينة من السنة).

**الحقول الإضافية على كل `block`:**
- `from_month` (1–12)
- `to_month` (1–12)

**صيغة الحساب:**
```
for each block:
    if invoice_date.month ∈ [from_month..to_month]:
        apply block normally (as in block mode)
    else:
        skip this block
```

**مثال:** شركة زراعية:
- شريحة الصيف (يونيو–سبتمبر): 0–200 kWh بسعر 0.30، فوق 200 بسعر 0.45 (لأن الضخ الزراعي).
- شريحة الشتاء (ديسمبر–فبراير): 0–500 kWh بسعر 0.10 (دعم).

الفاتورة الصادرة في يوليو تأخذ شرائح الصيف فقط. الفاتورة الصادرة في يناير تأخذ شرائح الشتاء فقط.

**متى يُستخدم:** الزراعة، السياحة، العقود ذات الموسمية الواضحة (تكييف/تدفئة).

---

### 8.5) `tou` — حسب وقت الاستخدام (Time of Use)
**الفكرة:** سعر kWh يتغير حسب **ساعة الاستهلاك خلال اليوم**، وليس الشهر أو الكمية.

**الحقول الإضافية على كل `block`:**
- `time_from` (float بالساعات، مثال 8.0 = 8 صباحاً)
- `time_to` (float بالساعات، مثال 20.0 = 8 مساءً)

**صيغة الحساب:**
```
تقرأ القراءة لكل ساعة (hourly intervals) أو لكل فترة:
  for each hour h in billing period:
      block = block where h ∈ [time_from..time_to]
      energy_h += consumption_h
      energy_charge += energy_h × block.price_per_kwh
```

**الفترات النموذجية:**
- **Off-Peak** (10 مساءً – 8 صباحاً): أرخص سعر.
- **Mid-Peak** (8 صباحاً – 4 مساءً، و10–12 مساءً): سعر متوسط.
- **On-Peak** (4 – 10 مساءً): أعلى سعر.

**مثال (عقد سكني):**
| الفترة | الوقت | السعر/kWh |
|---|---|---|
| Off-Peak | 22:00 – 08:00 | 0.10 |
| Mid-Peak | 08:00 – 16:00 | 0.20 |
| On-Peak | 16:00 – 22:00 | 0.35 |

استهلاك يومي 30 kWh (10 Off + 10 Mid + 10 On):
```
energy = 10×0.10 + 10×0.20 + 10×0.35 = 6.5
```

**متى يُستخدم:** العملاء التجاريون والصناعيون، محطات شحن السيارات الكهربائية، المنشآت التي يمكنها تحويل استهلاكها لأوقات الذروة.

---

### 8.6) مصفوفة مقارنة سريعة

| النمط | محور التغيير | الشريحة | الحقول الإضافية على block | التعقيد الحسابي |
|---|---|---|---|---|
| `flat` | لا شيء | — | — | منخفض |
| `block` | كمية الاستهلاك | تدريج (كل شريحة بسعرها) | `from_kwh`, `to_kwh` | متوسط |
| `tier` | كمية الاستهلاك | مستوى (شريحة واحدة للجميع) | `from_kwh`, `to_kwh` | متوسط |
| `seasonal` | الشهر | تدريج + تصفية شهرية | + `from_month`, `to_month` | متوسط |
| `tou` | الساعة | تدريج + تصفية زمنية يومية | + `time_from`, `time_to` | عالٍ (يتطلب قراءات بالساعة) |

### 8.7) حقول التسعير العامة (مشتركة بين كل الأنماط)

تُضاف على `utility.contract.template` بغض النظر عن النمط:
- `fixed_charge` (رسم ثابت شهري لا يتأثر بالاستهلاك)
- `service_charge` (رسم خدمة إضافية)
- `min_charge` / `max_charge` (حدود Floor/Cap للمبلغ النهائي قبل الضريبة)
- `effective_date` / `end_date` (صلاحية القالب، تُستخدم في `is_active` المحسوب)

> **حقول محذوفة من الخطة** (لا حاجة لها حالياً):
> - ~~`tax_percentage`~~ — الضريبة تُدار عبر نظام ضرائب Odoo القياسي (`account.tax` على بنود أمر البيع)، لا داعي لحقل مكرر.
> - ~~`fuel_adjustment`~~ — إن طُلب لاحقاً، يُضاف كبند `utility.contract.template.line` بنوع `service_charge` أو `formula` مرتبط بمؤشر وقود، وليس كحقل ثابت على القالب.
>
> تبعات الإزالة:
> - دالة `calculate_kwh()` في `utility_tariff.py:99-103` تُختصر إلى: `total = energy_charge + fixed_charge + service_charge`.
> - `utility_sale_order.py:274-280` يُحذف حساب الضريبة المحلي، وتُترك الضريبة لـ Odoo tax engine.
> - `utility_pos_order.py:17` (`fuel_adjustment` على POS) — يُحذف الحقل؛ إن لزم يُضاف كبند POS.
> - قسم `meter_line_type` في `utility.contract.template.line` يُبسَّط إلى: `consumption | fixed_fee | service_charge | discount` (إزالة `tax`).

### 8.8) خطة الترحيل — حقل `tariff_type` → `pricing_mode`

| القيمة القديمة | القيمة الجديدة |
|---|---|
| `flat` | `flat` |
| `block` | `block` |
| `tier` | `tier` |
| `seasonal` | `seasonal` |
| `tou` | `tou` |

التطابق 1:1، لا حاجة لتحويل دلالي. فقط تسمية الحقل.

---

## 8.9) `utility.formula` — طبقة المعادلات الديناميكية فوق أنماط التسعير

> `utility.formula` **نموذج مستقل بذاته** ولا يُدمج في `utility.contract.template` ضمن هذه الخطة. لكنه **يرتبط مباشرة** بقالب العقد عبر `utility.contract.template.line.qty_formula_id` و`utility.contract.template.line.formula_code`، ولهذا من الضروري فهم دوره قبل الدمج لأنه **الطبقة التي تتجاوز** المنطق الثابت للأنماط الخمسة أعلاه.

### 8.9.1) ما هو `utility.formula`؟

كود Python يُنفَّذ عبر `safe_eval()` لحساب **كمية** (qty) أو **سعر** (price) لبند عقد بشكل ديناميكي، بدلاً من استخدام قيمة ثابتة من `specific_price` أو من حقول التسعير العامة على القالب.

**النموذج (`utility_core/models/utility_formula.py`):**
- `name` (اسم وصفي)
- `code` (كود Python)
- `contract_line_count` (عدد البنود التي تستخدمه)
- زر `action_view_contract_lines` لفتح البنود المرتبطة
- زر `action_test_formula` لتشغيل المعادلة في Wizard بمدخلات تجريبية
- دالة `execute(...)` التي تُرجع `(result, name)` — الكمية المحسوبة واسم اختياري

### 8.9.2) المتغيرات المتاحة داخل المعادلة

عند تنفيذ `formula.execute(...)` يتم تمرير قاموس `locals_dict` يحتوي:

| المتغير | النوع | الوصف |
|---|---|---|
| `consumption` | float | استهلاك الفترة الحالية (kWh) |
| `previous_reading` | float | القراءة السابقة |
| `current_reading` | float | القراءة الحالية |
| `tariff` | object | كائن التعرفة (سابقاً)، سيصبح `template` (كائن قالب العقد) بعد الدمج |
| `account` | object | كائن `utility.customer` |
| `category` | object | كائن `utility.subscriber` (نوع المشترك) |
| `line` | object | كائن `utility.contract.template.line` الحالي |
| `result` | float | **يجب** تعيينه داخل المعادلة بقيمة المخرَج |
| `name` | str | يمكن تغييره لوصف مخصص للبند في الفاتورة |

### 8.9.3) كيف يُستخدم فعلياً؟

في `utility_billing/models/utility_recurring_invoice.py` (السطر 20-32):

```python
elif line.price_type == 'formula' and line.qty_formula_id:
    category = account.subscriber_id
    qty, computed_name = line.qty_formula_id.execute(
        consumption=consumption,
        previous_reading=reading.previous_reading,
        current_reading=reading.reading_value,
        tariff=tariff,
        account=account,
        category=category,
        line=line,
    )
```

والبند في القالب:
- `price_type = 'formula'`
- `qty_formula_id = <formula>`
- أو بدلاً منه: `formula_code` (نص Python مباشر) للحالات البسيطة.

### 8.9.4) العلاقة بين المعادلات وأنماط التسعير الخمسة

`utility.formula` **لا تحل محل** نمط التسعير — بل تتعاون معه:

```
utility.contract.template  ← يحدد pricing_mode (flat/block/tier/seasonal/tou)
        │
        ├── template.price_per_kwh      # سعر افتراضي
        ├── template.block_ids          # شرائح (لـ block/tier/seasonal/tou)
        │
        └── line_ids (utility.contract.template.line)
                ├── price_type = 'fixed' | 'from_product' | 'meter_reading' | 'formula'
                ├── meter_line_type = 'consumption' | 'fixed_fee' | 'service_charge' | 'discount'
                └── qty_formula_id (اختياري)  ← يحل محل السعر/الكمية الثابتة
```

**القاعدة:** نمط التسعير يحسب **إفتراضياً** سعر كWh والرسوم الثابتة. المعادلة تتدخل فقط عندما يحتاج بند معين لمنطق مخصص (مثلاً: خصم متدرج، إنذار تجاوز حد، حساب شرائح معقدة).

### 8.9.5) أمثلة عملية

**مثال 1: خصم 10% إذا الاستهلاك تجاوز 500 kWh**
```python
if consumption > 500:
    result = consumption * 0.10  # 10% من الاستهلاك كخصم
    name = "خصم ولاء (10% على ما فوق 500 kWh)"
else:
    result = 0.0
```

**مثال 2: رسم إنذار على الفواتير المتأخرة**
```python
if account.balance_due > 0:
    result = 50.0  # رسم ثابت
    name = "رسم تذكير بالفاتورة المتأخرة"
else:
    result = 0.0
```

**مثال 3: بند خدمة محسوب من الاستهلاك (مثل: رسوم صرف صحي مرتبطة بالاستهلاك)**
```python
result = consumption * 0.05  # 5 هللات لكل kWh
name = f"رسم صرف صحي ({consumption} kWh)"
```

**مثال 4: خصم حكومي حسب فئة المشترك**
```python
if category.code == 'GOV':
    result = consumption * tariff.price_per_kwh * 0.5  # 50% دعم
    name = "دعم حكومي 50%"
else:
    result = 0.0
```

### 8.9.6) أمان التنفيذ

- يُستخدم `safe_eval()` (وليس `eval()`) — لا وصول للوحدات الحساسة (`os`, `subprocess`...).
- `nocopy=True` لمنع تسريب الكائنات.
- `try/except` يلقط الأخطاء ويسجلها في `_logger.warning` ويعيد `0.0` (لا يكسر الفاتورة).
- `Wizard اختبار` (`formula_test_wizard`) يسمح بمدخلات تجريبية قبل الاعتماد.

### 8.9.7) تأثير خطة الدمج على `utility.formula`

| العنصر | الإجراء في خطة الدمج |
|---|---|
| موقع `utility.formula` نفسه | **يبقى** نموذجاً مستقلاً في `utility_core`. لا يُدمج. |
| اسم المتغير `tariff` في `locals_dict` | **يُعاد تسميته** إلى `template` (كائن `utility.contract.template`)، مع إبقاء alias `tariff` = `template` للتوافق في الإصدار الانتقالي. |
| `action_view_contract_lines` | **يبقى** (ما زال يفتح `utility.contract.template.line`). |
| `form_code` على `line` | **يبقى** كنص Python اختياري على البند. |
| `qty_formula_id` على `line` | **يبقى** كـ M2O بدون تغيير. |
| الـWizard `formula_test_wizard` | **يُحدَّث** وسيط الإدخال ليسمح باختيار قالب عقد بدلاً من تعرفة. |

### 8.9.8) ملخص — أين تقع المعادلات في البنية الجديدة؟

```
utility.contract.template                      [النمط: pricing_mode]
   │
   ├── حقول التسعير العامة                     [price_per_kwh, fixed_charge, ...]
   ├── block_ids (utility.contract.template.block)  [الشرائح التدريجية]
   │
   └── line_ids (utility.contract.template.line)
         │
         ├── price_type = 'meter_reading'      ← النمط الأساسي، يقرأ من حقول القالب
         ├── price_type = 'fixed'              ← مبلغ ثابت
         ├── price_type = 'from_product'       ← من سعر منتج Odoo
         └── price_type = 'formula'            ← يفوّض لـ utility.formula
                  │
                  └── qty_formula_id ─→ utility.formula.execute(...)
                                            [قاعدة Python ديناميكية]
```

> **الخلاصة:** أنماط التسعير الخمسة (`flat|block|tier|seasonal|tou`) تحدد **القاعدة الافتراضية**، و`utility.formula` يضيف **طبقة استثناءات** فوقها لبنود معينة تحتاج منطقاً مخصصاً. كلاهما يعيش على `utility.contract.template` (أو داخل بنوده) بعد الدمج، مع استقلالية كاملة لنموذج `utility.formula`.

---

## 8.10) تحليل البيانات الفعلية في `utility.contract.template.line`

> مراجعة للبيانات الحية في `utility_core/data/utility_sample_data.xml` (السطور 282–341) ومطابقتها مع الحقول المعرَّفة في `utility_contract_template.py` (السطور 128–165) ومع الاستهلاك الفعلي في `utility_sale_order.py` (السطور 220–284) و`utility_recurring_invoice.py` (السطور 5–58).

### 8.10.1) العينة الحالية (5 بنود، 2 قالب)

| السطر | القالب | sequence | price_type | meter_line_type | qty_formula_id | specific_price | is_subsidized |
|---|---|---|---|---|---|---|---|
| 282 | `res` (سكني) | 10 | `meter_reading` | `consumption` | `formula_consumption` | — | — |
| 291 | `res` (سكني) | 20 | `fixed` | `fixed_fee` | `formula_fixed_fee` | 1500.00 | — |
| 301 | `res` (سكني) | 30 | `fixed` | `discount` | `formula_discount` | -350.00 | True |
| 323 | `com` (تجاري) | 10 | `meter_reading` | `consumption` | `formula_consumption` | — | — |
| 332 | `com` (تجاري) | 20 | `fixed` | `fixed_fee` | `formula_fixed_fee` | 2500.00 | — |

### 8.10.2) المعادلات الفعلية (في `utility_subscriber_data.xml:60-84`)

```python
# formula_fixed_fee: ارجع 1.0 إذا كان فيه استهلاك، وإلا 0.0
if consumption > 0: result = 1.0
else:               result = 0.0

# formula_consumption: ارجع الاستهلاك كما هو
result = consumption

# formula_discount: أول 100 kWh مدعومة، ارجع الكمية "المخصومة"
units = consumption or 0.0
if units < 100: result = units      # كل الاستهلاك ضمن الدعم
else:           result = 100.0      # سقف 100 وحدة فقط
```

### 8.10.3) الفجوات المكتشفة بين الكود والبيانات

عند مطابقة الكود مع البيانات الفعلية، ظهرت **5 ملاحظات جوهرية** تؤثر على خطة الدمج:

#### 🔴 فجوة 1: `specific_price` يُتجاهل عند وجود `qty_formula_id`

- في `utility_recurring_invoice.py:12-15` الحلقة تمر على `line_ids` وتستخدم `line.specific_price or 0.0` كقيمة ابتدائية.
- لكن عندما `price_type='fixed'` و`meter_line_type='fixed_fee'` و**يوجد** `qty_formula_id`، فإن الكود في السطر 20-32 يستدعي المعادلة أولاً، ثم `price = line.specific_price or 0.0` يبقى دون تغيير.
- **المحصلة:** في البند `demo_contract_template_res_line2` قيمة `specific_price=1500.00` لا تُستخدم — المعادلة تُرجع `result=1.0` (الكمية) و`name` دون سعر. السعر الفعلي للـ kWh يأتي من خارج البند (عبر `tariff` في `utility_sale_order.py:264`).
- **النتيجة الفعلية في الفاتورة:** منتج "رسم ثابت" بكمية 1.0 وسعر `tariff.fixed_charge` (وليس `specific_price`).
- **تأثير على خطة الدمج:** يجب أن نقرر بشكل صريح:
  - (أ) `specific_price` يُستخدم كـ **سعر افتراضي** للبنود `fixed`/`discount` فقط حين لا توجد معادلة.
  - (ب) السعر الفعلي يأتي دائماً من `template.price_per_kwh` / `template.fixed_charge` / `template.service_charge` (مصدر واحد للحقيقة).
  - **المقترح:** الخيار (ب) — يُحذف `specific_price` من البند، أو يُحوَّل إلى `override_price` يُستخدم فقط حين يُراد تجاوز السعر من القالب.

#### 🔴 فجوة 2: البند `discount` يحمل `specific_price` بالسالب

- `demo_contract_template_res_line3` فيه `specific_price=-350.00` و`meter_line_type='discount'`.
- في `utility_sale_order.py:240` `is_tax = line.meter_line_type == 'tax'` — لا يوجد معالجة لخصم.
- في `utility_recurring_invoice.py:38-43` البند يُضاف إلى `order_line` بنفس الإشارة (السالب يبقى سالب).
- **المشكلة:** حساب `amount_energy/fixed/service` في السطور 242-247 لا يحسب `meter_line_type == 'discount'` في أي خانة — المبلغ السالب يذهب إلى `amount_energy` (افتراضي) ويسبب إرباكاً في التقارير.
- **تأثير على خطة الدمج:** إضافة خانة `amount_discount` على `sale.order`، أو اجبار البند الخصم على إنشاء `order_line` بـ `price_unit = -|specific_price|` مع `is_tax` يحيده من الإجمالي الفرعي.

#### 🟡 فجوة 3: `price_type='formula'` (المنصوص في الكود) لا يُستخدم في البيانات

- في `utility_contract_template.py:141-146` الحقل يحدد 4 قيم: `fixed | from_product | formula | meter_reading`.
- البيانات الفعلية تستخدم `meter_reading` و`fixed` فقط — ولا توجد بنود `price_type='formula'` رغم أن المنطق في `utility_recurring_invoice.py:20-32` مكتوب لها.
- **الاستنتاج:** الكود `price_type='formula'` **نظري**، في حين النمط العملي هو: `price_type='meter_reading'` + `qty_formula_id` (كما في `res_line1`).
- **تأثير على خطة الدمج:** خياران:
  - (أ) الإبقاء على `price_type='formula'` كـ **آلية override صريحة** للقالب (الـ `meter_line_type='formula'` يضيف فقط).
  - (ب) دمج المنطق في `price_type='meter_reading'` فقط: وجود `qty_formula_id` يعني "احسب الكمية من المعادلة"؛ عدم وجوده يعني "احسب من `consumption` المباشر". تبسيط.
  - **المقترح:** الخيار (ب) — يُحذف `price_type='formula'` ويُستعاض بشرط `if line.qty_formula_id` (كما في الكود الحالي للسطر 20).

#### 🟡 فجوة 4: `is_subsidized` مع `meter_line_type='discount'` يخلق ازدواجية

- `demo_contract_template_res_line3` يجمع بين `meter_line_type='discount'` و`is_subsidized=True` و`qty_formula_id=formula_discount`.
- في `utility_recurring_invoice.py:33-36` يوجد فرع مستقل:
  ```python
  elif line.is_subsidized and account.subscriber_id:
      qty, price, name = category._get_subsidized_amount(consumption, tariff)
  ```
- **المشكلة:** هذا الفرع **لا يتحقق** من `meter_line_type` — أي بند `is_subsidized=True` (حتى لو كان `consumption`) سيُستبدل بكمية/سعر من `_get_subsidized_amount`، متجاوزاً بذلك كل من المعادلة و`specific_price`.
- **الترتيب الحالي للتنفيذ** في `utility_recurring_invoice.py:11-37`:
  1. تحديد qty/price/name ابتدائيين من `line.quantity` و`line.specific_price`.
  2. إذا `meter_line_type='consumption'` و tariff موجود → qty=consumption, price=tariff.price_per_kwh.
  3. **وإلا إذا** `price_type='formula'` و qty_formula_id → تنفيذ المعادلة.
  4. **وإلا إذا** `is_subsidized` و category يدعم → حساب من `_get_subsidized_amount`.
- لاحظ: الشروط `elif`، لذا بند الخصم المدعوم (`is_subsidized=True` + `meter_line_type='discount'`) يدخل في الفرع 4 لأن `meter_line_type != 'consumption'`.
- **تأثير على خطة الدمج:** توحيد السلوك: `is_subsidized` يعمل فقط عندما `meter_line_type='discount'`. الفرع 4 يصبح فرعاً لـ `discount` فقط.

#### 🟢 فجوة 5: حقول `formula_code` و`qty_formula_id` متكرران

- في `utility_contract_template.py:148-150` يوجد `formula_code` (نص) **و** `qty_formula_id` (M2O).
- البيانات تستخدم `qty_formula_id` فقط، ولا يوجد استخدام لـ `formula_code` في أي ملف آخر.
- **الاستنتاج:** `formula_code` حقل ميت أو قيد التطوير.
- **تأثير على خطة الدمج:** يُحذف `formula_code`، ويُترك `qty_formula_id` كآلية وحيدة.

### 8.10.4) خطة الدمج — التحديثات بناءً على البيانات الفعلية

| القرار | الإجراء | رقم المرحلة المتأثرة |
|---|---|---|
| توحيد `price_type` → `meter_reading` فقط كقيمة افتراضية (مع `qty_formula_id` كاختياري) | حذف `price_type='formula'` و`from_product` | مرحلة 1 + 5 |
| حذف `formula_code` | حذف الحقل | مرحلة 1 |
| جعل `is_subsidized` يعمل **فقط** مع `meter_line_type='discount'` | تعديل قيد في `_onchange` أو `domain` | مرحلة 4 |
| التعامل مع `specific_price` كـ override صريح (وإلا فالسعر من القالب) | توثيق السلوك في `compute` توضيحي أو `_compute_specific_price` | مرحلة 4 |
| إضافة `amount_discount` على `sale.order` (أو تمييز `is_discount` على line) | تعديل `utility_sale_order.py:240` ليتعامل مع `discount` صراحة | مرحلة 4 |
| تبسيط `meter_line_type` إلى: `consumption \| fixed_fee \| service_charge \| discount` | تم (8.7) | — |

### 8.10.5) مخطط التدفق الفعلي بعد التصحيح (النسخة النهائية)

```
for each line in template.line_ids:
    qty   = 0.0
    price = 0.0
    name  = line.name or product.name

    if line.meter_line_type == 'consumption':
        qty   = line.qty_formula_id.execute(...).result   # أو consumption مباشرة
        price = template.price_per_kwh                    # مصدر الحقيقة

    elif line.meter_line_type == 'fixed_fee':
        if line.qty_formula_id:
            qty = line.qty_formula_id.execute(...).result
        else:
            qty = line.quantity
        price = line.specific_price or template.fixed_charge

    elif line.meter_line_type == 'service_charge':
        qty   = 1.0
        price = line.specific_price or template.service_charge

    elif line.meter_line_type == 'discount':
        if line.is_subsidized and account.subscriber_id and account.subscriber_id.subsidized_enabled:
            qty, price, name = account.subscriber_id._get_subsidized_amount(consumption, template)
        else:
            qty   = 1.0
            price = -(line.specific_price or 0.0)         # يُسجل كقيمة سالبة

    # amount_* = qty * price
```

هذا التدفق يعكس **ما تفعله البيانات فعلاً** مع تنظيف المنطق وإزالة التكرار.

---

## 8.11) متطلبات العمل الفعلية (من المستخدم)

> قبل تنفيذ الدمج، يجب توثيق "ما يجب أن يفعله النظام" كما يفهمه المستخدم، حتى نُحاذي الكود مع الواقع التشغيلي.

### 8.11.1) البنود الافتراضية لأي عقد

أي قالب عقد يحتوي، بالحد الأدنى، البنود التالية:

| # | البند | الطبيعة | طريقة الحساب |
|---|---|---|---|
| 1 | **رسم خدمة ثابت** | مبلغ ثابت لا يتأثر بالاستهلاك | `price × 1.0` (الكمية 1) |
| 2 | **استهلاك** | متغير حسب القراءة | `consumption × price_per_kwh` — حيث `price_per_kwh` يأتي من التعرفة/القالب |
| 3 | **شرائح تدريجية** (إن وُجدت) | متغير حسب قيمة الاستهلاك | كل kWh يُسعَّر بسعر شريحته (تدريج تصاعدي/تنازلي) |
| 4 | **الرسوم المحلية/البلدية** (مثال: رسوم النظافة أو التحسين) | متغير حسب الاستهلاك | `consumption × local_fee_per_kwh` (سعر ثابت × الاستهلاك) |
| 5 | **المعلم** (مثال: رسم خدمات تعليمية أو مجلس محلي) | متغير حسب الاستهلاك | `consumption × mu_allim_fee_per_kwh` |
| 6 | **النظافة** | متغير حسب الاستهلاك | `consumption × cleaning_fee_per_kwh` |
| 7 | **شرائح الخصم/الدعم** (حتى 100 kWh مثلاً) | خصم يذهب للجهة الداعمة | القيمة بالسالب — `(-discount_amount)` |

### 8.11.2) القواعد التشغيلية

1. **رسم الخدمة الثابت** = مبلغ واحد شهري لكل حساب (لا علاقة له بالاستهلاك).
2. **الاستهلاك** = `consumption × price_per_kwh` دائماً، **مهما كان نمط التسعير** (flat/block/tier...).
3. **الشرائح التدريجية** (إن وُجدت) تحل محل `price_per_kwh` الموحد للاستهلاك — حسب النمط:
   - `block` → كل شريحة بسعرها (تجميع).
   - `tier` → كل kWh بسعر آخر شريحة وصلها الاستهلاك.
   - `seasonal` → تُطبَّق الشرائح الموسمية فقط حسب شهر الفاتورة.
   - `tou` → تُطبَّق الشرائح الزمنية حسب ساعة الاستهلاك.
4. **الرسوم المحلية (المعلم/النظافة/المجلس المحلي)** = تُحسب دائماً كـ `consumption × fee_per_kwh` (مبلغ ثابت على القالب). **لا تتأثر** بالشرائح التدريجية — تُضاف على الفاتورة كبنود مستقلة.
5. **شرائح الخصم/الدعم**:
   - مثال: "أول 100 kWh تُخصم على الجهة الداعمة".
   - الحساب: إذا `consumption <= 100` فالخصم = `consumption × discount_rate`؛ وإلا فالخصم = `100 × discount_rate`.
   - البند في الفاتورة يظهر **بالسالب** (`price_unit < 0`) لأن الجهة الداعمة تسدد هذا الجزء.

### 8.11.3) مثال فاتورة واقعية (سكني، استهلاك 250 kWh)

| البند | الحساب | المبلغ |
|---|---|---|
| رسم خدمة ثابت | ثابت على القالب (مثلاً 1500) | 1500 |
| استهلاك (نمط block، 3 شرائح: 0-100 @ 0.15 / 100-300 @ 0.25 / >300 @ 0.40) | 100×0.15 + 150×0.25 | 52.5 |
| رسوم محلية (مجلس محلي) | 250 × 0.05 | 12.5 |
| رسوم النظافة | 250 × 0.02 | 5.0 |
| المعلم | 250 × 0.03 | 7.5 |
| **خصم الدعم** (أول 100 kWh) | -100 × 0.15 | **-15.0** |
| **الإجمالي قبل الضريبة** | | 162.5 |

> ملاحظة: الضريبة تُحسب خارج هذا الجدول عبر `account.tax` على بنود أمر البيع (لا تظهر كحقل محلي).

### 8.11.4) تفسير البنود الفعلية في ضوء هذا النموذج

| بند العينة | الدور في النموذج أعلاه |
|---|---|
| `demo_contract_template_res_line1` (consumption + qty_formula=consumption) | **الاستهلاك** (بند 2) |
| `demo_contract_template_res_line2` (fixed_fee, 1500) | **رسم خدمة ثابت** (بند 1) |
| `demo_contract_template_res_line3` (discount, -350, is_subsidized) | **خصم الدعم** (بند 7) |

**البنود الناقصة في العينة (لكن مطلوبة في الواقع):**
- ❌ **الرسوم المحلية** (بند 4) — غير موجودة في أي قالب.
- ❌ **المعلم** (بند 5) — غير موجود.
- ❌ **النظافة** (بند 6) — غير موجود.
- ❌ **الشرائح التدريجية** (بند 3) — لا توجد بنود `block_ids` على القوالب الموجودة في العينة، رغم أن `utility.contract.template.tariff_id` يشير لتعرفة موجودة.

### 8.11.5) متطلبات الدمج المحدثة

بناءً على ما سبق، خطة الدمج تحتاج التحديثات التالية:

| المتطلب | الموقع في الوثيقة | الإجراء |
|---|---|---|
| إضافة `meter_line_type='local_fee'` (أو `municipality`) | — | يستقبل `consumption × specific_price` |
| إضافة `meter_line_type='mu_allim'` | — | نفس المنطق — اختياري أو مدمج في `local_fee` |
| إضافة `meter_line_type='cleaning_fee'` | — | نفس المنطق |
| أو توحيدها كلها تحت `meter_line_type='local_fee'` مع `name` مميز (معلم/نظافة/مجلس) | — | المقترح: **توحيد** + حقل `local_fee_kind` (selection) |
| التأكد أن `block_ids` على القالب تُستخدم فعلاً عند `pricing_mode in ('block','tier','seasonal','tou')` | — | قسم 8.1–8.5 يغطي الحساب، يجب أن يُربط `consumption × price_per_kwh` (السطر 230 في `utility_sale_order.py`) بمنطق الشرائح |
| توحيد سلوك الخصم المدعوم في بند واحد | 8.10.4 | `meter_line_type='discount'` + `is_subsidized` |

### 8.11.6) نماذج بنود العقد الموسعة (النسخة النهائية المقترحة)

```
utility.contract.template.line
   ├── sequence
   ├── product_id
   ├── name
   ├── meter_line_type ∈ {
   │       'consumption',     # بند 2: consumption × price_per_kwh
   │       'fixed_fee',       # بند 1: رسم ثابت
   │       'service_charge',  # alias قديم
   │       'local_fee',       # بند 4/5/6: consumption × specific_price
   │       'discount'         # بند 7: بالسالب
   │   }
   ├── local_fee_kind ∈ {     # جديد، يظهر فقط حين meter_line_type='local_fee'
   │       'municipality', 'mu_allim', 'cleaning', 'other'
   │   }                     # يُترجَم إلى اسم البند في الفاتورة
   ├── price_type             # يُبسَّط إلى: 'fixed' | 'meter_reading'
   ├── specific_price         # override صريح، وإلا فمن القالب
   ├── qty_formula_id         # اختياري: override للكمية
   └── is_subsidized          # يعمل فقط مع meter_line_type='discount'
```

**حقول على القالب نفسه:**

```
utility.contract.template
   ├── pricing_mode           # flat | block | tier | seasonal | tou
   ├── price_per_kwh          # يُستخدم في 'consumption' و كقيمة افتراضية
   ├── fixed_charge           # يُستخدم في 'fixed_fee'
   ├── service_charge         # alias للتوافق
   ├── min_charge / max_charge
   ├── local_fee_per_kwh      # جديد: السعر الموحد للرسوم المحلية (اختياري)
   ├── local_fee_mu_allim     # جديد: رسم المعلم (اختياري)
   ├── local_fee_cleaning     # جديد: رسم النظافة (اختياري)
   ├── discount_first_units   # جديد: عدد الوحدات المدعومة (افتراضي 100)
   ├── discount_unit_value    # جديد: قيمة الخصم للوحدة (مثلاً 0.15)
   ├── block_ids              # شرائح تدريجية لـ block/tier/seasonal/tou
   ├── effective_date / end_date / is_active
   └── line_ids
```

### 8.11.7) سيناريوهات يجب اختبارها بعد الدمج

1. **سكني Flat بدون شرائح** — استهلاك 250 kWh، بدون رسوم محلية → 5 بنود (ثابت + استهلاك + 3 رسوم محلية افتراضية؟).
2. **سكني Block مع 3 شرائح** — استهلاك 250 kWh، شرائح + رسم محلي + خصم دعم لأول 100 → حساب تدريجي صحيح.
3. **تجاري Tier** — استهلاك 500 kWh، مستوى واحد + معلم.
4. **زراعي Seasonal** — استهلاك 400 kWh في شهر 7، شريحة الصيف فقط.
5. **صناعي TOU** — استهلاك يومي 100 kWh (موزّع على 3 فترات).
6. **بدون استهلاك** — قراءة صفر → رسم ثابت فقط، بدون أي بند استهلاك/خصم/محلي.
7. **خصم دعم كامل** — استهلاك 80 kWh (أقل من 100) → كل الكمية مدعومة.
8. **خصم دعم جزئي** — استهلاك 250 kWh → 100 kWh فقط مدعومة.

---

## 9) أسئلة يجب حسمها قبل البدء

1. هل `utility.tariff.category` تُنقل إلى `utility.subscriber` كحقل `category_id`، أم تُحذف وتُستخدم `subscriber.category_id` إن وُجد؟ (المقترح: الثاني).
2. هل نحتاج إبقاء `utility.tariff` بشكل دائم كـ alias للتكاملات الخارجية، أم نحذفه بعد 6 أشهر؟ (المقترح: alias دائم لتفادي الكسر).
3. هل `contract_template.line` يجب أن يدعم `pricing_mode='formula'` بشكل مستقل عن `qty_formula_id`؟ (المقترح: نعم، توسيع `price_type`).
4. ما هو مصير `pricelist_id` و`journal_id` على `utility.contract.template`؟ (يبقيان كما هما، لا علاقة لهما بالدمج).
