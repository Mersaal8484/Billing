# تحليل الفجوات - خطة تطوير Utility ERP

> مقارنة بين `C:\odoo18\odoo\pec_custom\pec` و `C:\odoo\odoo\odoo\utility_erp`
> تاريخ: 27 يونيو 2026

---

## 1. محرك القواعد (Rule Engine) - فجوة حرجة ❌

**PEC:** نظام متكامل لإدارة قواعد الأعمال (7 موديلات)
| الموديل | الوصف |
|---------|-------|
| `rule.engine.rule` | قاعدة رئيسية مع دورة حياة (draft→active→paused→deprecated) |
| `rule.engine.rule.version` | إصدارات القاعدة مع JSON conditions |
| `rule.engine.action` | 14 نوع إجراء (SMS, suspend, reactivate, write_field, hold_invoice, flag_fraud, create_task, ...) |
| `rule.engine.execution.log` | سجل تنفيذ كامل |
| `rule.engine.fact.snapshot` | لقطة بيانات وقت التنفيذ |
| `rule.engine.service` (Abstract) | محرك التقييم: build_facts() ← evaluate_condition() ← dispatch_action() |
| `pec.barcode.ocr.service` (Abstract) | فك الباركود و OCR لصور العدادات |

**Utility ERP:** لا يوجد

**المطلوب:**
- [ ] إنشاء `utility.rule.engine` موديل متكامل
- [ ] دعم المشغلات (event-based + time-based)
- [ ] 3 نطاقات: `utility.account`, `utility.bill`, `utility.payment`
- [ ] 10+ أنواع إجراءات (تعليق، إرسال SMS، إنشاء مهمة، إشعار، ...)
- [ ] لوحة تحكم لسجل التنفيذ
- [ ] Fact building مع JSON snapshot
- [ ] وضع simulation/dry_run للاختبار

---

## 2. عقود الاشتراك المتكررة (Recurring Contracts) - فجوة كبيرة ❌

**PEC:** `account.analytic.contract` + `account.analytic.contract.line`
- إنشاء فواتير متكررة (pre-paid / post-paid)
- إنشاء أوامر بيع متكررة
- قوالب عقود مع بنود متغيرة
- جداول قراءات مرتبطة بالعقد
- Billing periods (شهري/نصف شهري/ربع سنوي)
- علاقة مباشرة مع `account.analytic.account`

**Utility ERP:** لا يوجد نظام عقود متكررة

**المطلوب:**
- [ ] إنشاء `utility.contract` موديل
- [ ] إنشاء `utility.contract.line` للبنود
- [ ] ربط مع `utility.account`
- [ ] دعم auto-generate bills
- [ ] دعم auto-generate sales for prepaid
- [ ] Billing periods configuration

---

## 3. التكامل مع موديولات Odoo الأساسية 🔗

### 3.1 account.analytic.account (PEC: 50+ حقل إضافي)
| الخاصية | PEC | Utility ERP |
|---------|-----|-------------|
| اسم العداد | `meter_id` | حقول العداد في `utility.meter` |
| رقم العقد | `meter_contractid` | - |
| قراءة العداد | `meter_current_reading` | - |
| استخدام العداد | `meter_uses` | - |
| فاز العداد | `meter_vastype` | في `utility.meter` |
| المحول | `transformer_id` | - |
| قيمة العداد | `meter_val` | - |
| الباركود | `barcode` / `barcode_image` | - |
| التوقيع | `customer_signature` | - |
| الفئة | `subscriber_category_id` | - |
| المستوى | `level` (subscriber/transformer_cell) | - |
| الحالة | `state` (new/active/suspended/closed) | - |
| الأقساط | `subscription_price` | - |
| التسعير | `price_per_kilo` | - |
| تاريخ العقد | `date_contract`, `date_sub_start` | - |

**المطلوب:**
- [ ] إضافة حقول `utility.account` إضافية (نوع الفاز، رقم العقد، الباركود، التوقيع)
- [ ] ربط `utility.account` مع `account.analytic.account`
- [ ] دعم `account.analytic.account` لنظام NUTS

### 3.2 account.move (PEC: 25+ حقل)
| الخاصية | PEC | Utility ERP |
|---------|-----|-------------|
| قراءة العداد | `last_meter_reading`, `current_meter_reading` | - |
| وحدات الاستهلاك | `consumption_units` | - |
| صورة العداد | `meter_image`, `meter_image_secondary` | - |
| حالة الصورة | `image_state` | - |
| NUTS الموقع | `nuts1_id`..`nuts4_id` | - |
| فترة الفاتورة | `date_range_id`, `period_end_date` | - |
| المتأخرات | `previous_arrears` | - |
| الفرق | `consumption_difference`, `consumption_diff_percentage` | - |
| التحقق | `reviewer_id`, `route_number` | - |
| المحصل | `workflow_process_id` | - |

### 3.3 account.payment (PEC: 15+ حقل)
- `pec_payment_method` (manual/electronic)
- `electronic_doc_no`, `electronic_payment_date`
- `electronic_bank_id`, `electronic_transfer_ref`
- `is_invoice_verified` (التحقق من الفاتورة)

### 3.4 sale.order / product.template
- `sale.order.type` + `sale.order.type.rule` (تصنيف أوامر البيع)
- `sale.workflow.process` (سير عمل آلي)
- `product.template.is_contract`, `contract_template_id`

### 3.5 res.partner (PEC: 25+ حقل)
- `nickname`, `is_subscriber`
- `last_payment`, `last_invoice` (compute)
- `char_code`, `old_payment`, `old_credit`
- `reading_multiplier`, `tariff_code`
- `subscription_amount_partner`
- `NUTS multi-level fields`
- `payment_token_id` (للدفع الآلي)

---

## 4. إدارة التركيبات الكهربائية (NUTS Hierarchy) 🏗️

**PEC:** `res.partner.nuts` - 4 مستويات:
1. منطقة (Level 1)
2. فرع (Level 2)
3. مربع/محول (Level 3)
4. حي/مجمع سكني (Level 4)

**Utility ERP:** 8 مستويات ولكن:
- `utility.region` ← `utility.area` ← `utility.zone` ← `utility.office` ← `utility.substation` ← `utility.feeder` ← `utility.transformer` ← `utility.route`

**الفجوة:**
- [ ] PEC يستخدم `_parent_store` مع `parent_path` للتسلسل الهرمي
- [ ] PEC يربط NUTS مباشرة مع `account.analytic.account`
- [ ] PEC لديه `is_branch`, `sms_name`, `billing_period` لكل موقع
- [ ] PEC لديه `level3_type` (public/private/government/other)
- [ ] PEC يدير عقود الخلايا `cell_contract_id`
- [ ] Utility ERP يفتقد `parent_store` للتسلسل الهرمي

---

## 5. خدمة الباركود و OCR 📷

**PEC:** `pec.barcode.ocr.service` (Abstract)
- `decode_barcode()` ← pyzbar
- `perform_ocr_on_meter_image()` ← pytesseract

**Utility ERP:** لا يوجد

**المطلوب:**
- [ ] إنشاء `utility.barcode.ocr.service` abstract model
- [ ] تكامل مع Odoo's barcode scanning
- [ ] معالجة صور العدادات (قراءة تلقائية)

---

## 6. استبدال العدادات (Meter Replacement) 🔄

**PEC:** موديل كامل مع معالج
- `meter.replace.history` لتسجيل كل استبدال
- `meter.replace.wizard` لتنفيذ الاستبدال
- يحسب الاستهلاك غير المفوتّر
- ينشئ قراءة إغلاق للعداد القديم

**Utility ERP:** لا يوجد

**المطلوب:**
- [ ] `utility.meter.replacement` موديل
- [ ] `utility.meter.replacement.wizard` معالج
- [ ] حساب الاستهلاك غير المفوتّر
- [ ] تسجيل قراءة الإغلاق والافتتاح

---

## 7. التسويات (Settlements) 🏛️

### 7.1 تسوية القراءات (Reading Settlement)
**PEC:**
- `reading.settlement.wizard`: تعديل قراءة + إنشاء سجل
- `reading.settlement.log`: سجل جميع التعديلات

### 7.2 التسوية المالية (Financial Settlement)
**PEC:**
- `financial.settlement.wizard`: إنشاء قيد محاسبي للغرامات/الخصومات

**Utility ERP:** لا يوجد

**المطلوب:**
- [ ] `utility.reading.settlement.wizard`
- [ ] `utility.reading.settlement.log`
- [ ] `utility.financial.settlement.wizard` (غرامات + خصومات)

---

## 8. تقارير متقدمة 📊

**PEC:**
- **Transformer Balance Report**: تحليل الفاقد في المحولات (QWeb-PDF, Arabic RTL)
- **Customer Activity Statement**: كشف حساب المشترك

**Utility ERP:**
- فقط إيصال دفع بسيط

**المطلوب:**
- [ ] تقرير توازن المحولات (Transformer Loss Analysis)
- [ ] كشف حساب المشترك
- [ ] تقرير مناطق NUTS
- [ ] تقرير أداء المحصلين
- [ ] تقرير الفاقد في الشبكة
- [ ] تقارير ذكية SQL-view (مثل `utility_prepaid_electricity`)

---

## 9. التوليد الآلي للفواتير (Crons) ⏰

**PEC (9 crons):**
| الكرون | الفاصل | الوظيفة |
|--------|--------|---------|
| Automatic Workflow | 1 min | تشغيل سير العمل الآلي |
| Recurring Invoice (×3) | 1 hour | إنشاء فواتير متكررة لكل منطقة |
| Recurring Sale | 1 day | إنشاء أوامر بيع متكررة |
| Retry Auto Pay | 30 min | إعادة محاولة الدفع الآلي |
| Batch Reading Invoicing | 1 day | فوترة جماعية للقراءات |
| Batch Collection SMS | 1 hour | حملات SMS للتحصيل (مُعطل) |

**Utility ERP (1 cron):**
- `cron_generate_bills_daily` (مرة يومياً)

**المطلوب:**
- [ ] زيادة عدد crons لتغطية:
  - [ ] توليد الفواتير المتكررة حسب الدورة (شهري/ربع سنوي)
  - [ ] إعادة محاولة الدفع التلقائي
  - [ ] مراقبة الأرصدة المنخفضة (Low credit alarm)
  - [ ] تحديث حالة الفواتير المتأخرة
  - [ ] إرسال تنبيهات SMS/بريد للمتأخرين

---

## 10. الإعدادات (Settings) ⚙️

**PEC:** 11 معامل في `res.config.settings`:
| المعامل | config_parameter |
|---------|-----------------|
| مجموعة التحقق | `pec.check_group_id` |
| مراجعة صورة العداد | `pec.meter_review_required` |
| إلزامية صورة العداد | `pec.meter_image_mandatory` |
| نسبة الفاقد المسموح | `pec.max_transformer_loss_tolerance` |
| تأكيد الفاتورة تلقائياً | `pec.enable_auto_invoice_confirm` |
| حساب الغرامات | `pec.fine_account_id` |
| حساب الخصومات | `pec.discount_account_id` |
| إعادة محاولة الدفع | `pec.max_auto_pay_retries` |
| حد الاستهلاك العالي | `pec.high_consumption_threshold` |
| SMS عند الفاتورة | `pec.send_sms_on_invoice` |
| SMS عند الدفع | `pec.send_sms_on_payment` |

**Utility ERP:** لا توجد إعدادات مخصصة

**المطلوب:**
- [ ] صفحة إعدادات خاصة بـ Utility (تحت قائمة Configuration)
- [ ] 15+ معامل قابل للتخصيص

---

## 11. الفئات والتصنيفات 🏷️

**PEC:**
- `pec.subscriber.category`: فئتين (category/subcategory) مع هرمية
- `res.partner.sector`: قطاع المشترك
- `sale.order.type` + `sale.order.type.rule`: تصنيف أوامر البيع
- Billing periods لكل منطقة

**Utility ERP:**
- `utility.tariff.category` فقط

**المطلوب:**
- [ ] `utility.subscriber.category` مع هرمية ثنائية المستوى
- [ ] `utility.partner.sector` قطاعات
- [ ] ربط الفئات مع `utility.customer` و `utility.account`

---

## 12. الدفع الإلكتروني والتحقق 🔐

**PEC:**
- `payment_token_id` على الـ partner (بوابة دفع)
- `is_auto_pay` مع `auto_pay_retries` و `auto_pay_retry_hours`
- Electronic payment tracking (bank, transfer ref, etc.)
- `is_invoice_verified` آلية التحقق من صحة الفاتورة

**Utility ERP:**
- `utility.payment` بسيط مع طرق دفع أساسية

**المطلوب:**
- [ ] تكامل payment.acquirer مع `utility.payment`
- [ ] دفع آلي متكرر مع إعادة محاولة
- [ ] تتبع المدفوعات الإلكترونية
- [ ] آلية التحقق من صحة الفواتير

---

## 13. التوثيق والاختبارات 🧪

**PEC:**
- 4 فئات اختبار لمحرك القواعد (341 سطر)
- وثائق متعددة (README, master plan, operational docs, user guide AR)

**Utility ERP:**
- لا يوجد أي اختبارات
- لا يوجد توثيق

**المطلوب:**
- [ ] اختبارات لكل موديل (unit tests + integration tests)
- [ ] وثائق API
- [ ] دليل المستخدم بالعربية
- [ ] خطة التشغيل

---

## 14. تحسينات أمان إضافية 🔒

**PEC:**
- 4 مستويات لأمان محرك القواعد (Viewer→Author→Publisher→Admin)
- `base.group_system` للوصول الكامل للموديلات الحساسة
- مدير التسويات `group_pec_settlement_manager`

**Utility ERP:**
- 9 مجموعات صلاحية ولكن بعضها لا يستخدم فعلياً
- `group_no_one` (R) مستخدم بشكل غريب في utility_prepaid

**المطلوب:**
- [ ] مراجعة توزيع الصلاحيات
- [ ] إضافة group للمشرفين الماليين
- [ ] إضافة group لمدير التسويات
- [ ] إعادة النظر في `base.group_user` للوصول CRU للمعاملات المالية

---

## 15. حالات الطوارئ (Emergency Credit) 🆘

**PEC:**
- لا يوجد نظام رصيد طوارئ في PEC (يعتمد على auto-pay)

**Utility ERP:**
- `utility.adjustment` لديه emergency_credit والكن غير مكتمل

**المطلوب:**
- [ ] تفعيل وحدة رصيد الطوارئ
- [ ] حدود الرصيد الطارئ حسب فئة المشترك
- [ ] جدولة السداد التلقائي بعد فترة السماح
- [ ] إشعارات SMS عند منح رصيد الطوارئ

---

## 16. عقود الخلايا (Transformer Cells) ⚡

**PEC:**
- `account.analytic.account` يدعم نوع `transformer_cell`
- `cell_ids` (one2many) ← `parent_meter_id`
- `child_contract_ids` ← `parent_meter_id`
- نسب التوزيع: `main_percentage`, `sub_percentage`
- عقود خاصة بالخلية: `cell_contract_id` على NUTS level3

**Utility ERP:**
- لا يوجد مفهوم للخلايا أو العقود الفرعية

**المطلوب:**
- [ ] دمج مفهوم خلايا المحولات
- [ ] عقود فرعية مع نسب توزيع
- [ ] حسابات الاستهلاك حسب النسبة

---

## 17. معالجة الصور والملفات 📎

**PEC:**
- `ir.attachment` معدل لدعم `image_url`, `custom_storage_path`
- صور العدادات مرتبطة بالقراءات والفواتير
- توقيع العملاء (صور)
- `image_state` (clear/not_clear/not_same/none/replace/loss_read)

**Utility ERP:**
- يستخدم `ir.attachment` الأساسي فقط

**المطلوب:**
- [ ] تحسين إدارة تخزين الصور
- [ ] ربط الصور بالقراءات والفواتير
- [ ] حالات فحص الصور

---

## 18. إدارة المستخدمين والحقول الإضافية 👤

**PEC:**
- `res.users`: `x_numblock`, `x_userx`, `prevent_installment`, `nuts1_ids`
- تقييد بعض المستخدمين (مثل منع التقسيط)

**Utility ERP:**
- `utility.staff` + `utility.user.role` فقط (لا توجد حقول إضافية على `res.users`)

---

## ملخص أولويات التطوير

| الأولوية | المكون | الجهد | التأثير |
|----------|--------|-------|---------|
| 🔴 1 | **محرك القواعد** (Rule Engine) | عالي | حاسم - أتمتة الأعمال |
| 🔴 2 | **العقود المتكررة** | عالي | حاسم - الفوترة الدورية |
| 🔴 3 | **Settings & Configuration** | متوسط | مهم - تخصيص النظام |
| 🟡 4 | **تكامل account.analytic.account** | عالي | مهم - الربط المحاسبي |
| 🟡 5 | **Crons & Automation** | متوسط | مهم - التشغيل الآلي |
| 🟡 6 | **استبدال العدادات** | متوسط | مهم - الصيانة |
| 🟢 7 | **التسويات (Settlements)** | متوسط | مفيد - التصحيحات |
| 🟢 8 | **تقارير متقدمة** | متوسط | مفيد - التحليل |
| 🟢 9 | **توليد الفواتير (CRONs)** | منخفض | مفيد - الأتمتة |
| 🟢 10 | **الباركود و OCR** | منخفض | مفيد - القراءة التلقائية |
| 🟢 11 | **الدعم الإلكتروني** | متوسط | مفيد |
| 🟢 12 | **اختبارات + توثيق** | منخفض | أساسي |

---

## هيكلة الملفات المقترحة للإضافات

```
utility_erp/
├── utility_core/
│   ├── models/
│   │   ├── utility_settings.py          ← NEW (res.config.settings)
│   │   ├── utility_contract.py           ← NEW
│   │   ├── utility_contract_line.py      ← NEW
│   │   ├── utility_subscriber_category.py ← NEW
│   │   ├── utility_barcode_ocr.py        ← NEW
│   │   └── utility_meter_replacement.py  ← NEW
│   ├── views/
│   │   ├── utility_settings_views.xml    ← NEW
│   │   ├── utility_contract_views.xml    ← NEW
│   │   ├── utility_subscriber_category_views.xml ← NEW
│   │   └── utility_reports.xml           ← NEW
│   └── data/
│       └── utility_settings_data.xml     ← NEW
├── utility_operations/
│   ├── models/
│   │   ├── utility_readings_settlement.py ← NEW
│   │   └── utility_financial_settlement.py ← NEW
│   ├── wizards/
│   │   ├── reading_settlement_wizard.py  ← NEW
│   │   └── financial_settlement_wizard.py ← NEW
│   └── views/
│       ├── reading_settlement_views.xml  ← NEW
│       └── financial_settlement_views.xml ← NEW
├── utility_billing/
│   ├── models/
│   │   ├── utility_recurring_invoice.py  ← NEW
│   │   └── utility_auto_pay.py           ← NEW
│   └── data/
│       └── utility_cron_extras.xml       ← NEW
├── utility_rule_engine/                  ← NEW MODULE
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models/
│   │   ├── rule_engine_rule.py
│   │   ├── rule_engine_version.py
│   │   ├── rule_engine_action.py
│   │   ├── rule_engine_execution_log.py
│   │   ├── rule_engine_fact.py
│   │   └── rule_engine_service.py
│   ├── views/
│   │   ├── rule_engine_views.xml
│   │   └── rule_engine_menus.xml
│   ├── security/
│   │   ├── rule_engine_security.xml
│   │   └── ir.model.access.csv
│   ├── data/
│   │   ├── rule_engine_demo.xml
│   │   └── rule_engine_sequence.xml
│   ├── tests/
│   │   └── test_rule_engine.py
│   └── static/description/icon.png
└── reports/                             ← Shared reports
    ├── transformer_balance_report.xml
    └── customer_statement_report.xml
```
