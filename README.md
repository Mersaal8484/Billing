# Utility ERP

نظام ERP مبني على Odoo 16 لإدارة شركات توزيع الكهرباء، ويغطي العملاء والمشتركين والعدادات والشبكات والقراءات والفوترة والتحصيل والبيع المسبق.

## المكونات

يحتوي المشروع على الوحدات التالية:

1. `date_range` — إدارة الفترات الزمنية.
2. `utility_core` — البيانات الأساسية، العملاء، الحسابات، العدادات، التعريفات، الشبكات، القوالب، المعادلات، الإعدادات، ولوحات المعلومات.
3. `utility_inventory` — ربط العدادات بالمخزون والمنتجات والدفعات.
4. `utility_operations` — أوامر الخدمة، الفحص، العبث، الاستبدال، وتسويات القراءات.
5. `utility_billing` — الفوترة الآجلة، أوامر البيع، القراءات، الغرامات، التحصيل، الفواتير المتكررة، بوابة الدفع، والبوابة الإلكترونية.
6. `utility_prepaid` — البيع المسبق، رموز STS، نقاط البيع، الورديات، والمدفوعات.

> لا توجد وحدة مستقلة باسم `utility_migration`. نماذج الترحيل موجودة داخل `utility_core`.

## ترتيب التثبيت

يجب تثبيت الوحدات بالترتيب التالي:

```text
date_range
utility_core
utility_inventory
utility_operations
utility_billing
utility_prepaid
```

يجب تثبيت `utility_core` قبل بقية وحدات Utility ERP.

## المتطلبات

- Odoo 16.0
- PostgreSQL
- Python المتوافق مع نسخة Odoo المستخدمة
- الحزم الموجودة في `requirements.txt`:

```text
xlsxwriter
openpyxl
requests
odoo-test-helper
```

لتثبيت الحزم:

```bash
pip install -r requirements.txt
```

## التشغيل والتثبيت

أضف مسار المشروع إلى `addons_path` ثم نفّذ التثبيت من بيئة Odoo:

```bash
odoo-bin -d <database> -i utility_core --stop-after-init
odoo-bin -d <database> -i utility_inventory --stop-after-init
odoo-bin -d <database> -i utility_operations --stop-after-init
odoo-bin -d <database> -i utility_billing --stop-after-init
odoo-bin -d <database> -i utility_prepaid --stop-after-init
```

عند تعديل ملفات وحدة مثبتة، استخدم الترقية:

```bash
odoo-bin -d <database> -u utility_billing --stop-after-init
```

أوقف أي عملية Odoo أخرى تستخدم نفس قاعدة البيانات قبل الترقية لتجنب أخطاء `SerializationFailure`.

## أهم سير العمل

### القراءات والفوترة

تمر القراءة بالحالات التالية:

```text
draft → under_review → approved → queued → billed
```

القراءات التجارية القابلة للفوترة تُدار من النموذج الموحد `utility.reading`. توجد قائمة مستقلة لمراجعة الفواتير التجارية، بينما يبقى نموذج القراءات العام بتصميمه الأساسي.

### الفوترة الآجلة

الفاتورة الآجلة مبنية على توريث `sale.order`، وليست نموذجًا مستقلاً باسم `utility.bill`.

- بنود الفاتورة تستخدم `sale.order.line`.
- الدفعات تستخدم `account.payment`.
- حالة الفاتورة التشغيلية محفوظة في `bill_state`.
- حساب البنود يتم من خلال `_calculate_amounts()`.
- منتجات الخدمات الكهربائية تُفوتر حسب الكمية المطلوبة، ولا تتطلب تسليمًا مخزنيًا.

### البيع المسبق

البيع المسبق مبني على Odoo POS:

- `utility.token` يرتبط بـ `pos.order`.
- الورديات ترتبط بأوامر POS والمدفوعات.
- إنشاء الرمز يتم عند إكمال أمر POS.

## النماذج الرئيسية

| المجال | النموذج |
|---|---|
| العميل/الحساب | `utility.customer` |
| العداد | `utility.meter` |
| القراءة الموحدة | `utility.reading` |
| القالب التعاقدي | `utility.contract.template` |
| الفترة | `date.range` |
| الفاتورة الآجلة | `sale.order` |
| الدفعة | `account.payment` |
| الغرامة | `utility.penalty` |
| رمز البيع المسبق | `utility.token` |

## المراجعة التجارية

قائمة المراجعة المستقلة تعتمد على `utility.reading` وتعرض القراءات التجارية القابلة للفوترة فقط، مع:

- الصورة والقراءات والاستهلاك.
- حالة الصورة وحالة المراجعة.
- اعتماد أو رفض القراءة.
- نموذج مختصر خاص بالقائمة دون تغيير نموذج القراءات الأساسي.

## API

توفر `utility_billing` واجهات REST للفوترة تحت المسار:

```text
/api/v1/utility/billing/*
```

كما تدعم استقبال قراءات AMI من خلال نقطة callback مخصصة.

تستخدم نقاط API `sudo()` فقط عند الحاجة لعبور صلاحيات البوابة، مع التحقق من ملكية السجل والشريك قبل إرجاع البيانات.

## الأمان والشركات

- جميع النماذج التجارية الجديدة يجب أن تحتوي على `company_id` عند الحاجة.
- يتم تطبيق قواعد الشركات المتعددة على السجلات.
- مجموعات الصلاحيات مرتبة هرميًا من القراءة فقط حتى مدير النظام.
- لا تستخدم `sudo()` لتجاوز تصميم الصلاحيات.
- لا يوجد اعتماد على البريد الإلكتروني لإشعارات العملاء؛ الإشعارات تمر عبر SMS أو مزود WhatsApp المحلي.

## الاختبارات

اختبارات المشروع موجودة في:

```text
utility_core/tests/
utility_billing/tests/
```

تشغيل اختبارات وحدة:

```bash
odoo-bin -d <test_database> -i utility_core --test-enable --stop-after-init
odoo-bin -d <test_database> -i utility_billing --test-enable --stop-after-init
```

## بيانات العينة والفترات

تتضمن بيانات العينة فترات شهرية ونصف شهرية. يجب أن تتطابق `billing_cadence` مع دورية المنطقة:

```text
monthly      → monthly
biweekly     → semi_monthly
```

إذا لم توجد مناطق نشطة لدورية معينة، يمكن إنشاء الفترة بدون نطاق مناطق ثم ضبط النطاق من الإعدادات.

## ملاحظات التطوير

- استخدم ORM بدل SQL قدر الإمكان.
- تجنب البحث داخل حلقات التكرار.
- استخدم `read_group()` للتجميعات.
- أضف الفهارس للحقول المستخدمة بكثرة في النطاقات والتقارير.
- لف رسائل المستخدم في `_()` للترجمة.
- استخدم `logging` بدل `print()` في كود الإنتاج.
- لا تستخدم البريد الإلكتروني القياسي لإشعارات العملاء.

## ملفات مرجعية

- `EXECUTION_PLAN.md` — خطة التنفيذ.
- `GAP_ANALYSIS_PLAN.md` — تحليل الفجوات.
- `utility_core/security/utility_security.xml` — مجموعات الأمان.
- `utility_billing/models/utility_sale_order.py` — الفوترة المبنية على أوامر البيع.
- `utility_billing/models/utility_reading.py` — إنشاء الفواتير من القراءات.
- `utility_billing/views/commercial_invoice_review_views.xml` — قائمة مراجعة الفواتير التجارية.
