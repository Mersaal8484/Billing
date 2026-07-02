# نقل نموذج `utility.reading` إلى الوحدة الأساسية utility_core

## تاريخ التعديل
2026-07-02

## سبب التعديل
خلل في بدء تشغيل Odoo (`KeyError: 'feeder_id'`) بسبب وجود حقول `One2many` في `utility.feeder` (المعرفة في `utility_core`) تشير إلى `utility.reading` (المعرفة في `utility_billing`). عند تحميل الوحدات، يتم تحميل `utility_core` أولاً، ولكن `utility.reading` غير محمّل بعد، مما يسبب تعطلاً في `setup_nonrelated` داخل `fields.py`.

## ملخص التغييرات

### 1. إنشاء نموذج أساسي في utility_core
**الملف:** `utility_core/models/utility_reading.py` (جديد)
- `_name = 'utility.reading'`
- يحتوي على جميع الحقول البنيوية الأساسية (meter_id, customer_id, account_id, reading_date, reading_value, consumption, reading_category, transformer_id, feeder_id, state, ...)
- يحتوي على الطرق الأساسية: `_compute_consumption`, `_compute_consumption_analysis`, `_compute_previous_reading`, `action_submit_review`, `action_approve`, `action_reject`, `action_approve_batch`
- لا يحتوي على `batch_id` (خاص بالفوترة)
- لا يحتوي على طرق الفوترة: `action_generate_bill`, `action_generate_bills_batch`, `action_requeue`, `_cron_generate_bills`

### 2. تحديث __init__.py
**الملف:** `utility_core/models/__init__.py`
- إضافة السطر: `from . import utility_reading`

### 3. تحديث نموذج الفوترة ليرث من النموذج الأساسي
**الملف:** `utility_billing/models/utility_reading.py`
- تغيير من `class UtilityReading(models.Model): _name = 'utility.reading'`
- إلى `class UtilityReading(models.Model): _inherit = 'utility.reading'`
- إضافة `batch_id` (Many2one إلى `utility.reading.batch`)
- إضافة طرق الفوترة: `action_generate_bill`, `action_generate_bills_batch`, `action_requeue`, `_cron_generate_bills`

### 4. إصلاح حقول One2many في utility.customer
**الملف:** `utility_core/models/utility_customer.py`
- تغيير 4 حقول من `utility.transformer.reading` (نموذج محذوف) إلى `utility.reading`:
  - `coupling_reading_ids`: `('utility.transformer.reading', 'customer_id')` ← `('utility.reading', 'account_id')`
  - `cell_reading_ids`: `('utility.transformer.reading', 'customer_id')` ← `('utility.reading', 'account_id')`
  - `uploaded_reading_ids`: `('utility.transformer.reading', 'customer_id')` ← `('utility.reading', 'account_id')`
  - `billed_reading_ids`: `('utility.transformer.reading', 'customer_id')` ← `('utility.reading', 'account_id')`
- تحديث domains لاستخدام حالات `utility.reading`:
  - `('reading_type', '=', 'coupling')` ← `('reading_category', 'in', ['transformer', 'feeder'])`
  - `('reading_type', '=', 'cell')` ← `('reading_category', '=', 'transformer')`
  - `('state', 'in', ['draft', 'confirmed'])` ← `('state', 'in', ['draft', 'under_review', 'approved'])`
  - `('state', '=', 'confirmed')` ← `('state', '=', 'billed')`

### 5. تحديث شاشة الفيدر
**الملف:** `utility_core/views/utility_feeder_views.xml`
- تحديث صفحة "قراءات الربط":
  - `name` ← `reading_id`
  - إزالة `reading_type`
  - `decoration-success="state == 'confirmed'"` ← `decoration-success="state == 'approved'"`
  - `decoration-danger="state == 'cancelled'"` ← `decoration-danger="state == 'error'"`
  - `action_confirm` ← `action_submit_review`
- تحديث صفحة "قراءات المقارنة":
  - إزالة domain `('reading_type', '=', 'comparison')`
  - `name` ← `reading_id`
  - تحديث decorations

### 6. نقل صلاحيات الوصول (ACLs)
**الملف:** `utility_core/security/ir.model.access.csv`
- إزالة 4 سجلات لـ `model_utility_transformer_reading` (نموذج محذوف)
- إضافة 6 سجلات لـ `model_utility_reading`:
  - admin (group_utility_admin): 1,1,1,1
  - readonly (group_utility_readonly): 1,0,0,0
  - billing_manager (group_utility_billing_manager): 1,1,1,1
  - technician (group_utility_technician): 1,1,1,0
  - supervisor (group_utility_supervisor): 1,1,0,0
  - auditor (group_utility_auditor): 1,0,0,0

**الملف:** `utility_billing/security/ir.model.access.csv`
- إزالة 5 سجلات مكررة لـ `model_utility_reading`

### 7. تنظيف البيانات القديمة
**الملف:** `utility_core/data/utility_sequence.xml`
- إزالة تسلسل `seq_utility_transformer_reading` (رمز TFR) لأن النموذج `utility.transformer.reading` محذوف

## هيكل التبعيات بعد التعديل

```
utility_core
  ├── utility.reading (نموذج أساسي مع الحقول الأساسية)
  ├── utility.feeder (One2many إلى utility.reading) ← يعمل الآن
  └── utility.customer (One2many إلى utility.reading) ← يعمل الآن

utility_billing (يعتمد على utility_core)
  └── utility.reading (توريث، إضافة batch_id وطرق الفوترة)
```

## ملاحظات إضافية
- جميع شاشات `utility.reading` ما زالت في `utility_billing/views/utility_reading_views.xml`
- جميع صلاحيات `utility.reading.batch` ما زالت في `utility_billing/security/ir.model.access.csv`
- الكرون المجدول `_cron_generate_bills` ما زال في `utility_billing` (ضمن النموذج الموروث)
- تسلسل `utility.reading` ما زال في `utility_billing/data/utility_sequence.xml` (يتم إنشاؤه تلقائياً عند الحاجة)
