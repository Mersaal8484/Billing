# التعديل المعماري لموديول `utility_prepaid`

## 1. القرار المعماري

يجب تنفيذ جميع وظائف الدفع المسبق داخل موديول واحد:

```text
utility_prepaid
```

ويشمل ذلك:

* مبيعات الكهرباء مسبقة الدفع.
* تكامل نقاط البيع POS.
* محرك التسعير الخاص بالدفع المسبق.
* إدارة طلبات Vending.
* توليد وإدارة STS Tokens.
* التكامل مع مزودي STS.
* إدارة المعاملات المالية والتشغيلية.
* ورديات الكاشير.
* الاسترداد والعكس.
* تسويات الطاقة.
* استقطاع الديون.
* الإشعارات.
* بوابة العميل.
* واجهات API.
* تكامل AMI وMDMS المتعلق بالدفع المسبق.
* التقارير ولوحات المعلومات.
* القيود المحاسبية.
* المهام المجدولة والمصالحة.

لا يتم إنشاء موديولات فرعية مستقلة مثل:

```text
utility_prepaid_pos
utility_sts_gateway
utility_prepaid_portal
utility_ami_connector
```

لكن يتم تنظيم هذه الوظائف كحزم داخلية داخل نفس الموديول.

---

# 2. الاعتماديات الخارجية للموديول

يعتمد `utility_prepaid` على موديولات Odoo القياسية والموديولات الأساسية للنظام فقط:

```python
'depends': [
    'base',
    'mail',
    'account',
    'point_of_sale',
    'portal',
    'web',
    'product',
    'utility_core',
]
```

يمكن إضافة الاعتماديات التالية عند استخدامها فعلياً:

```python
'depends': [
    'base',
    'mail',
    'account',
    'point_of_sale',
    'portal',
    'web',
    'product',
    'contacts',
    'sms',
    'utility_core',
]
```

لا يجب ربط الموديول بموديولات غير ضرورية.

---

# 3. الهيكل الداخلي المقترح

```text
utility_prepaid/
│
├── __init__.py
├── __manifest__.py
├── README.md
│
├── models/
│   ├── __init__.py
│   │
│   ├── vending/
│   │   ├── __init__.py
│   │   ├── vending_request.py
│   │   ├── vending_charge_line.py
│   │   ├── vending_channel.py
│   │   ├── vending_policy.py
│   │   └── vending_service.py
│   │
│   ├── token/
│   │   ├── __init__.py
│   │   ├── utility_token.py
│   │   ├── sts_provider.py
│   │   ├── sts_transaction.py
│   │   ├── sts_service.py
│   │   └── key_change_campaign.py
│   │
│   ├── pos/
│   │   ├── __init__.py
│   │   ├── pos_order.py
│   │   ├── pos_session.py
│   │   └── cashier_shift.py
│   │
│   ├── accounting/
│   │   ├── __init__.py
│   │   ├── utility_transaction.py
│   │   ├── account_move.py
│   │   ├── account_payment.py
│   │   └── prepaid_accounting_service.py
│   │
│   ├── recovery/
│   │   ├── __init__.py
│   │   ├── debt_recovery_policy.py
│   │   ├── debt_recovery_line.py
│   │   └── debt_recovery_service.py
│   │
│   ├── reversal/
│   │   ├── __init__.py
│   │   ├── vending_reversal.py
│   │   ├── prepaid_adjustment.py
│   │   └── reversal_reason.py
│   │
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── ami_event.py
│   │   ├── prepaid_webhook.py
│   │   ├── integration_log.py
│   │   └── notification_service.py
│   │
│   ├── configuration/
│   │   ├── __init__.py
│   │   ├── res_company.py
│   │   ├── res_config_settings.py
│   │   └── prepaid_sequence.py
│   │
│   └── reporting/
│       ├── __init__.py
│       ├── prepaid_dashboard.py
│       ├── vending_report.py
│       └── sts_performance_report.py
│
├── services/
│   ├── __init__.py
│   ├── vending_engine.py
│   ├── tariff_adapter.py
│   ├── sts_gateway.py
│   ├── accounting_engine.py
│   ├── reconciliation_engine.py
│   ├── notification_engine.py
│   ├── security_service.py
│   └── idempotency_service.py
│
├── controllers/
│   ├── __init__.py
│   ├── prepaid_api.py
│   ├── prepaid_portal.py
│   ├── payment_callback.py
│   └── prepaid_webhook.py
│
├── wizards/
│   ├── __init__.py
│   ├── vending_retry_wizard.py
│   ├── vending_reversal_wizard.py
│   ├── prepaid_adjustment_wizard.py
│   ├── token_resend_wizard.py
│   ├── token_reprint_wizard.py
│   └── cashier_shift_close_wizard.py
│
├── security/
│   ├── utility_prepaid_security.xml
│   ├── ir.model.access.csv
│   └── prepaid_record_rules.xml
│
├── data/
│   ├── utility_prepaid_sequence.xml
│   ├── prepaid_products.xml
│   ├── prepaid_channels.xml
│   ├── prepaid_transaction_types.xml
│   ├── prepaid_reversal_reasons.xml
│   ├── prepaid_cron.xml
│   └── prepaid_mail_templates.xml
│
├── views/
│   ├── menus.xml
│   ├── vending_request_views.xml
│   ├── utility_token_views.xml
│   ├── sts_provider_views.xml
│   ├── sts_transaction_views.xml
│   ├── utility_transaction_views.xml
│   ├── cashier_shift_views.xml
│   ├── debt_recovery_policy_views.xml
│   ├── vending_reversal_views.xml
│   ├── prepaid_adjustment_views.xml
│   ├── ami_event_views.xml
│   ├── prepaid_dashboard_views.xml
│   ├── res_config_settings_views.xml
│   └── pos_order_views.xml
│
├── static/
│   ├── description/
│   │   ├── icon.png
│   │   └── index.html
│   │
│   └── src/
│       ├── js/
│       │   ├── prepaid_pos_models.js
│       │   ├── prepaid_pos_store.js
│       │   ├── prepaid_token_button.js
│       │   ├── prepaid_token_popup.js
│       │   ├── prepaid_status_popup.js
│       │   └── prepaid_receipt.js
│       │
│       ├── xml/
│       │   ├── prepaid_token_button.xml
│       │   ├── prepaid_token_popup.xml
│       │   ├── prepaid_status_popup.xml
│       │   └── prepaid_receipt.xml
│       │
│       └── scss/
│           └── prepaid_pos.scss
│
├── report/
│   ├── prepaid_receipt_report.xml
│   ├── vending_report_templates.xml
│   ├── token_report_templates.xml
│   └── cashier_shift_report.xml
│
├── tests/
│   ├── __init__.py
│   ├── test_vending_pricing.py
│   ├── test_vending_workflow.py
│   ├── test_sts_gateway.py
│   ├── test_idempotency.py
│   ├── test_pos_integration.py
│   ├── test_debt_recovery.py
│   ├── test_reversal.py
│   ├── test_adjustment.py
│   ├── test_accounting.py
│   ├── test_security.py
│   └── test_reconciliation.py
│
└── migrations/
    └── 16.0.x.x.x/
        ├── pre-migration.py
        └── post-migration.py
```

---

# 4. النماذج الأساسية داخل الموديول

## 4.1 طلب بيع الكهرباء

```python
utility.vending.request
```

يمثل المرجع المركزي لكل عملية بيع كهرباء مسبقة الدفع، سواء جاءت من:

* POS.
* بوابة العميل.
* موظف خدمة العملاء.
* تطبيق الهاتف.
* API.
* وكيل بيع.
* بوابة دفع إلكترونية.

### أهم العلاقات

```python
pos_order_id = fields.Many2one('pos.order')
payment_id = fields.Many2one('account.payment')
account_move_id = fields.Many2one('account.move')
shift_id = fields.Many2one('utility.cashier.shift')
token_ids = fields.One2many('utility.token', 'vending_request_id')
charge_line_ids = fields.One2many(
    'utility.vending.charge.line',
    'vending_request_id'
)
transaction_ids = fields.One2many(
    'utility.transaction',
    'vending_request_id'
)
sts_transaction_ids = fields.One2many(
    'utility.sts.transaction',
    'vending_request_id'
)
```

يظل هذا النموذج هو المصدر الرئيسي للحقيقة، وليس `pos.order`.

---

## 4.2 بنود احتساب الشحنة

```python
utility.vending.charge.line
```

يخزن تفاصيل توزيع المبلغ:

* قيمة الطاقة.
* رسوم الخدمة.
* الضرائب.
* رسوم الصيانة.
* استقطاع الديون.
* الغرامات.
* عمولة الوكيل.
* التقريب.
* الرسوم الأخرى.

---

## 4.3 رمز STS

```python
utility.token
```

يخزن:

* رمز التوكن.
* نوع التوكن.
* العداد.
* الحساب.
* كمية الطاقة.
* مرجع المزود.
* حالة الإصدار.
* حالة التسليم.
* سجل إعادة الإرسال.
* سجل إعادة الطباعة.
* الارتباط بطلب Vending.

---

## 4.4 مزود STS

```python
utility.sts.provider
```

يدعم تعدد مزودي STS داخل نفس الموديول.

### أنواع المزودين الممكنة

```python
provider_type = fields.Selection([
    ('generic_rest', 'Generic REST'),
    ('generic_soap', 'Generic SOAP'),
    ('hexing', 'Hexing'),
    ('inhemeter', 'Inhemeter'),
    ('landis_gyr', 'Landis+Gyr'),
    ('conlog', 'Conlog'),
    ('custom', 'Custom Provider'),
])
```

يجب ألا يحتوي `utility.vending.request` على كود خاص بمصنع معين.

يتم اختيار المنفذ المناسب داخل خدمة مركزية:

```python
services/sts_gateway.py
```

---

# 5. تصميم STS Gateway داخل الموديول الواحد

يحتوي `utility_prepaid` على واجهة عامة لمزودي STS:

```python
class STSGateway:

    def generate_credit_token(self, request):
        raise NotImplementedError

    def generate_management_token(self, request):
        raise NotImplementedError

    def query_transaction(self, provider_reference):
        raise NotImplementedError

    def reverse_transaction(self, transaction):
        raise NotImplementedError

    def health_check(self):
        raise NotImplementedError
```

ويتم تنفيذ مزودي STS في ملفات منفصلة داخل نفس الموديول:

```text
services/providers/
├── __init__.py
├── base_provider.py
├── generic_rest_provider.py
├── generic_soap_provider.py
├── hexing_provider.py
├── inhemeter_provider.py
├── landis_gyr_provider.py
└── custom_provider.py
```

الهيكل الكامل:

```text
services/
├── providers/
│   ├── base_provider.py
│   ├── generic_rest_provider.py
│   ├── generic_soap_provider.py
│   ├── hexing_provider.py
│   ├── inhemeter_provider.py
│   └── landis_gyr_provider.py
└── sts_gateway.py
```

بهذا يكون التكامل داخل `utility_prepaid`، مع بقاء الكود منظماً وقابلاً للاستبدال.

---

# 6. تكامل POS داخل الموديول

تتم وراثة النماذج التالية داخل `utility_prepaid`:

```python
pos.order
pos.session
pos.config
pos.payment
```

## الحقول المقترحة في `pos.order`

```python
is_prepaid_vending = fields.Boolean(
    string='Prepaid Electricity Vending'
)

utility_account_id = fields.Many2one(
    'utility.customer.account',
    string='Utility Account'
)

utility_meter_id = fields.Many2one(
    'utility.meter',
    string='Prepaid Meter'
)

vending_request_id = fields.Many2one(
    'utility.vending.request',
    string='Vending Request',
    copy=False
)

vending_amount = fields.Monetary(
    string='Vending Amount'
)

vending_kwh = fields.Float(
    string='Purchased kWh'
)

vending_status = fields.Selection(
    related='vending_request_id.state',
    store=True
)
```

## دور `pos.order`

يقتصر دور `pos.order` على:

* تسجيل عملية الدفع.
* ربط العملية بالكاشير والجلسة.
* طباعة الإيصال.
* إنشاء طلب Vending.
* عرض حالة إصدار التوكن.

لا يحتوي `pos.order` على منطق STS أو التسعير الأساسي.

---

# 7. نقطة البيع والمنتج

يتم تعريف منتج خدمة واحد مخصص لعملية الشحن:

```text
Prepaid Electricity Vending
```

ولا يتم البحث عنه بالاسم أو الكود بصورة ثابتة.

يتم تعريفه في إعدادات `pos.config` أو `res.company`:

```python
prepaid_vending_product_id = fields.Many2one(
    'product.product',
    string='Prepaid Vending Product'
)
```

## خصائص المنتج

* نوعه خدمة.
* غير مخزني.
* سعره يتم تحديده من محرك الشحن.
* لا يستخدم سعر قائمة الأسعار مباشرة.
* لا يسمح بتعديل سعره يدوياً إلا بصلاحية خاصة.
* يمكن إخفاؤه من شاشة المنتجات العادية.
* يضاف فقط من خلال زر «شحن كهرباء».

---

# 8. دورة العمل داخل الموديول

```text
POS / Portal / API
        ↓
Create Vending Quote
        ↓
Server-Side Tariff Calculation
        ↓
Create utility.vending.request
        ↓
Confirm Payment
        ↓
Queue Token Generation
        ↓
Call STS Provider
        ↓
Receive Token
        ↓
Create utility.token
        ↓
Create utility.transaction
        ↓
Create Accounting Entries
        ↓
Print / Send Token
        ↓
Complete Request
```

كل هذه العمليات موجودة داخل `utility_prepaid`.

---

# 9. محرك التسعير داخل `utility_prepaid`

يمكن أن يظل تعريف التعرفة الأساسي في `utility_core`، لأن الحساب والعقد والتعرفة بيانات مركزية.

لكن جميع قواعد احتساب شحنة الدفع المسبق توضع داخل:

```text
utility_prepaid/services/vending_engine.py
utility_prepaid/services/tariff_adapter.py
```

## وظيفة محرك التسعير

```python
def calculate_vending_quote(
    account,
    meter,
    amount,
    vending_date,
    channel=None,
    agent=None,
):
    pass
```

## النتيجة

```python
{
    'gross_amount': 100000,
    'energy_amount': 85000,
    'service_charge': 5000,
    'tax_amount': 2000,
    'debt_recovery_amount': 8000,
    'other_deduction_amount': 0,
    'net_vending_amount': 85000,
    'kwh_purchased': 425,
    'charge_lines': [],
    'tariff_snapshot': {},
}
```

يتم تخزين Snapshot كامل للتعرفة المستخدمة داخل طلب الشحن.

---

# 10. معادلة الشحن

لا يعتمد النظام دائماً على:

```text
kWh = (Amount - Service Charge) / Price per kWh
```

بل يدعم داخل `utility_prepaid`:

* التعرفة الثابتة.
* التعرفة ذات الشرائح.
* التعرفة ذات الشريحة الموحدة.
* الرسوم الثابتة.
* الضرائب.
* الدعم.
* الاستقطاعات.
* استرداد الديون.
* الحدود الدنيا والعليا.
* التقريب.
* التعرفة حسب فئة العميل.
* التعرفة حسب الجهد.
* التعرفة حسب المنطقة.
* التسعير حسب تاريخ العملية.

---

# 11. استقطاع الديون داخل الموديول

تتم إضافة النماذج التالية:

```python
utility.prepaid.debt.policy
utility.prepaid.debt.policy.line
utility.prepaid.debt.recovery
```

## طرق الاستقطاع

```python
recovery_method = fields.Selection([
    ('fixed', 'Fixed Amount'),
    ('percentage', 'Percentage'),
    ('full', 'Full Recoverable Debt'),
    ('installment', 'Installment'),
    ('priority', 'Priority Based'),
])
```

## الإعدادات

* نسبة الاستقطاع.
* الحد الأقصى لكل شحنة.
* الحد الأدنى للطاقة بعد الاستقطاع.
* أنواع الديون المشمولة.
* أولوية الديون.
* الحساب المحاسبي.
* تاريخ سريان السياسة.
* العميل أو الفئة المستهدفة.
* الفرع أو الشركة.

---

# 12. ورديات الكاشير

يتم الاحتفاظ بالنموذج:

```python
utility.cashier.shift
```

داخل نفس الموديول.

## الارتباطات

```python
pos_session_id = fields.Many2one('pos.session')

vending_request_ids = fields.One2many(
    'utility.vending.request',
    'shift_id'
)

postpaid_payment_ids = fields.Many2many(
    'account.payment',
    relation='utility_shift_account_payment_rel'
)
```

رغم أن الموديول للدفع المسبق، يمكن للوردية تسجيل تحصيلات الدفع الآجل إذا كان ذلك جزءاً من مسؤولية نفس الكاشير.

لكن يجب فصل الإجماليات:

```python
prepaid_cash_total
prepaid_bank_total
postpaid_cash_total
postpaid_bank_total
total_expected
total_counted
difference_amount
```

---

# 13. العكس والاسترداد

تتم إضافة:

```python
utility.vending.reversal
```

داخل `utility_prepaid`.

## المسار

```text
Draft
  ↓
Submitted
  ↓
Under Review
  ↓
Provider Validation
  ↓
Approved
  ↓
STS Reversal
  ↓
Financial Refund
  ↓
Reversed
```

لا يجوز تنفيذ الاسترداد بمجرد تصريح العميل بأنه لم يستخدم التوكن.

يجب:

* الاستعلام من مزود STS إن كان ذلك مدعوماً.
* التحقق من حالة التوكن.
* تطبيق سياسة الشركة.
* الحصول على موافقة.
* تنفيذ العكس لدى المزود.
* إنشاء القيد المالي العكسي.
* تسجيل الاسترداد.

---

# 14. تسويات الطاقة

يتم إضافة:

```python
utility.prepaid.adjustment
```

وتستخدم في:

* تعويض العميل.
* ترحيل الرصيد عند استبدال العداد.
* تصحيح خطأ تعرفة.
* معالجة توكن فاشل.
* تسوية نتيجة فحص فني.
* منح وحدات مجانية.
* خصم وحدات بصورة معتمدة.

لا يتم تعديل إحصائيات الحساب فقط.

يجب أن تنتج التسوية:

* Management Token عند الحاجة.
* سجل معاملة.
* قيد محاسبي إن كانت لها قيمة مالية.
* سجل تدقيق.
* موافقة حسب نوع وقيمة التسوية.

---

# 15. AMI وMDMS داخل الموديول

يتم تضمين الجزء المتعلق بالدفع المسبق فقط داخل `utility_prepaid`.

## النموذج

```python
utility.prepaid.ami.event
```

## أنواع الأحداث

```python
event_type = fields.Selection([
    ('low_credit', 'Low Credit'),
    ('zero_credit', 'Zero Credit'),
    ('token_accepted', 'Token Accepted'),
    ('token_rejected', 'Token Rejected'),
    ('meter_disconnected', 'Meter Disconnected'),
    ('meter_reconnected', 'Meter Reconnected'),
    ('tamper', 'Tamper Event'),
    ('balance_update', 'Balance Update'),
])
```

## الاستخدام

* إرسال تنبيه انخفاض الرصيد.
* تأكيد قبول التوكن.
* تحديث آخر رصيد معروف.
* معالجة رفض التوكن.
* فتح طلب دعم.
* ربط الحدث بالعداد والحساب والتوكن.

إدارة الشبكة والقراءات العامة يمكن أن تبقى في `utility_core` أو `utility_operations`، لكن أحداث الدفع المسبق الخاصة بالرصيد والتوكن تكون داخل `utility_prepaid`.

---

# 16. بوابة العميل داخل الموديول

تكون Controllers وTemplates الخاصة بالبوابة داخل `utility_prepaid`.

## خدمات البوابة

* عرض حسابات الدفع المسبق.
* عرض العدادات.
* شراء شحنة جديدة.
* عرض تفاصيل السعر.
* الدفع الإلكتروني.
* متابعة حالة العملية.
* نسخ التوكن.
* إعادة إرسال التوكن.
* تنزيل الإيصال.
* عرض سجل المشتريات.
* تقديم طلب مراجعة.
* عرض تنبيهات انخفاض الرصيد.

## المسارات

```text
/my/prepaid
/my/prepaid/accounts
/my/prepaid/account/<id>
/my/prepaid/vending/new
/my/prepaid/vending/<reference>
/my/prepaid/token/<id>
/my/prepaid/history
```

---

# 17. واجهات API داخل الموديول

تكون جميع API Controllers داخل:

```text
utility_prepaid/controllers/prepaid_api.py
```

## المسارات

```http
POST /api/v1/prepaid/quote
POST /api/v1/prepaid/vending
POST /api/v1/prepaid/vending/payment
GET  /api/v1/prepaid/vending/<reference>
POST /api/v1/prepaid/vending/<reference>/retry
POST /api/v1/prepaid/vending/<reference>/resend
POST /api/v1/prepaid/vending/<reference>/reversal
POST /api/v1/prepaid/ami/event
POST /api/v1/prepaid/sts/callback
```

## الحماية

* API key أو OAuth2 حسب البنية.
* Idempotency key.
* توقيع Webhook.
* صلاحيات القناة.
* Rate limiting.
* سجل تدقيق.
* إخفاء التوكن عن غير المخولين.
* منع إعادة استخدام الطلب.
* التحقق من الشركة والفرع.

---

# 18. المعاملات المالية

يحتوي الموديول على النموذج:

```python
utility.transaction
```

## أنواع المعاملات

```python
transaction_type = fields.Selection([
    ('vending', 'Vending'),
    ('fee', 'Fee'),
    ('tax', 'Tax'),
    ('debt_recovery', 'Debt Recovery'),
    ('reversal', 'Reversal'),
    ('refund', 'Refund'),
    ('adjustment', 'Adjustment'),
    ('compensation', 'Compensation'),
])
```

هذا النموذج سجل تشغيلي وليس بديلاً عن:

```python
account.move
account.payment
pos.payment
```

---

# 19. المحاسبة داخل الموديول

يتم تضمين خدمة المحاسبة داخل:

```text
utility_prepaid/services/accounting_engine.py
```

## سياسة الاعتراف عند البيع

```text
Debit: Cash / Bank / POS Receivable
Credit: Electricity Revenue
Credit: Service Charge Revenue
Credit: Tax Payable
Credit: Debt Receivable
```

## سياسة الإيراد المؤجل

عند البيع:

```text
Debit: Cash / Bank / POS Receivable
Credit: Prepaid Electricity Liability
Credit: Service Charge Revenue
Credit: Tax Payable
Credit: Debt Receivable
```

وعند وصول بيانات الاستهلاك:

```text
Debit: Prepaid Electricity Liability
Credit: Electricity Revenue
```

## إعدادات الحسابات

```python
prepaid_liability_account_id
electricity_revenue_account_id
service_charge_revenue_account_id
prepaid_tax_account_id
debt_recovery_account_id
prepaid_refund_account_id
prepaid_adjustment_account_id
agent_commission_account_id
```

توضع في `res.company` وتعرض عبر `res.config.settings`.

---

# 20. إعدادات الموديول

يجب أن يتضمن `utility_prepaid` صفحة إعدادات متكاملة.

## إعدادات البيع

```python
prepaid_vending_product_id
minimum_vending_amount
maximum_vending_amount
allow_multiple_meter_vending
require_selected_customer
require_open_cashier_shift
```

## إعدادات STS

```python
default_sts_provider_id
sts_request_timeout
sts_max_retry_count
sts_retry_interval
enable_automatic_retry
enable_provider_status_query
```

## إعدادات التوكن

```python
mask_token_in_tree_views
allow_token_reprint
token_reprint_limit
allow_token_resend
token_resend_limit
require_reprint_reason
```

## إعدادات المحاسبة

```python
prepaid_revenue_policy
prepaid_liability_account_id
electricity_revenue_account_id
service_charge_revenue_account_id
debt_recovery_account_id
refund_account_id
```

## إعدادات الديون

```python
enable_debt_recovery
default_debt_policy_id
minimum_energy_percentage
```

## إعدادات الإشعارات

```python
enable_token_sms
enable_token_email
enable_low_credit_alert
default_low_credit_threshold
```

---

# 21. القوائم داخل Odoo

```text
Prepaid Electricity
│
├── Dashboard
│
├── Vending
│   ├── Vending Requests
│   ├── Pending Requests
│   ├── Failed Requests
│   ├── Completed Requests
│   └── Vending Transactions
│
├── Tokens
│   ├── All Tokens
│   ├── Credit Tokens
│   ├── Management Tokens
│   ├── Failed Tokens
│   └── Key Change Tokens
│
├── Cashier Operations
│   ├── Cashier Shifts
│   ├── Open Shifts
│   ├── Shift Reconciliation
│   └── Cash Differences
│
├── Debt Recovery
│   ├── Recovery Policies
│   ├── Recovery Transactions
│   └── Customer Recoveries
│
├── Reversals & Adjustments
│   ├── Reversal Requests
│   ├── Adjustments
│   ├── Refunds
│   └── Reasons
│
├── STS Management
│   ├── Providers
│   ├── STS Transactions
│   ├── Failed Communications
│   ├── Provider Health
│   └── Key Change Campaigns
│
├── AMI Events
│   ├── Low Credit Events
│   ├── Token Acceptance Events
│   ├── Token Rejection Events
│   └── Tamper Events
│
├── Reports
│   ├── Sales Analysis
│   ├── kWh Sales
│   ├── Channel Analysis
│   ├── Cashier Performance
│   ├── Debt Recovery
│   ├── STS Performance
│   ├── Reversals
│   └── Accounting Reconciliation
│
└── Configuration
    ├── Settings
    ├── Vending Channels
    ├── STS Providers
    ├── Debt Policies
    ├── Reversal Reasons
    └── Notification Rules
```

---

# 22. الصلاحيات

## المجموعات

```text
Utility Prepaid User
Utility Prepaid Cashier
Utility Prepaid Supervisor
Utility Prepaid Officer
Utility STS Operator
Utility Reversal Approver
Utility Adjustment Approver
Utility Finance Reviewer
Utility Prepaid Manager
Utility Prepaid Auditor
Utility Prepaid Administrator
```

## الفصل بين الصلاحيات

* الكاشير ينشئ عمليات البيع ولا يعتمد العكس.
* المشرف يغلق الورديات ويراجع الفروقات.
* موظف STS يتابع أخطاء المزود دون تعديل المبالغ.
* مسؤول التسويات ينشئ التسوية ولا يعتمدها.
* المعتمد يوافق ولا ينشئ الطلب لنفسه.
* المدقق يملك صلاحية القراءة والتقارير فقط.
* إعدادات الاتصال متاحة للمسؤول التقني فقط.
* عرض التوكن الكامل يحتاج صلاحية خاصة.

---

# 23. المهام المجدولة

تكون جميع المهام داخل `utility_prepaid`.

## المهام المطلوبة

```text
Retry Failed STS Requests
Query Pending STS Transactions
Reconcile POS and Vending Requests
Reconcile STS Provider Transactions
Send Pending Token Notifications
Process Low Credit Alerts
Expire Unpaid Vending Requests
Detect Duplicate Provider References
Rebuild Prepaid Account Statistics
Generate Deferred Revenue Entries
Monitor Provider Health
```

كل مهمة يجب أن:

* تعمل على دفعات.
* تستخدم حدوداً زمنية.
* تسجل الأخطاء.
* لا تكرر العمليات الناجحة.
* تدعم Multi-company.
* تستخدم Idempotency.

---

# 24. قواعد منع التكرار

يجب إضافة القيود التالية:

```python
_sql_constraints = [
    (
        'vending_idempotency_unique',
        'unique(company_id, idempotency_key)',
        'The vending idempotency key must be unique per company.'
    ),
    (
        'provider_reference_unique',
        'unique(provider_id, provider_reference)',
        'The STS provider reference must be unique.'
    ),
]
```

ويجب ألا يعتمد النظام على قاعدة البيانات فقط.

تقوم خدمة `idempotency_service.py` بـ:

* البحث عن الطلب السابق.
* إعادة النتيجة السابقة.
* الاستعلام من المزود عند الحالة المعلقة.
* منع إصدار توكن جديد.
* رفع حالة تعارض عند اختلاف المبالغ.

---

# 25. واجهة POS

يحتوي الموديول على:

```text
PrepaidTokenButton
PrepaidTokenPopup
PrepaidPricingDetails
PrepaidTokenStatusPopup
PrepaidFailedTokenPopup
PrepaidReceipt
```

## تدفق الواجهة

```text
Select Customer
      ↓
Click Prepaid Recharge
      ↓
Search Customer Accounts
      ↓
Select Account and Meter
      ↓
Enter Amount
      ↓
Get Server Quote
      ↓
Show Charges and kWh
      ↓
Confirm
      ↓
Create POS Line
      ↓
Pay Order
      ↓
Create Vending Request
      ↓
Generate Token
      ↓
Print Receipt
```

---

# 26. تحميل البيانات في POS

لا يتم تحميل جميع الحسابات والعدادات عند بدء جلسة POS.

يتم تحميل:

* إعدادات الموديول.
* منتج الشحن.
* صلاحيات المستخدم.
* القنوات.
* الحد الأدنى والأقصى.
* إعدادات العرض.

ويتم البحث عن الحسابات عند الطلب بواسطة RPC باستخدام:

* رقم العميل.
* رقم الحساب.
* رقم العداد.
* الهاتف.
* اسم المشترك.

هذا يمنع بطء POS عند وجود مئات الآلاف من المشتركين.

---

# 27. الإيصال

يتم تصميم إيصال الدفع المسبق داخل `utility_prepaid`.

## البيانات

* اسم الشركة.
* الفرع.
* رقم العملية.
* مرجع POS.
* مرجع STS.
* اسم المشترك.
* رقم الحساب.
* رقم العداد.
* المبلغ المدفوع.
* الضرائب.
* رسوم الخدمة.
* استقطاع الديون.
* صافي الطاقة.
* كمية kWh.
* رمز التوكن.
* QR Code.
* التاريخ والوقت.
* الكاشير.
* طريقة الدفع.
* تعليمات الاستخدام.

## عرض التوكن

```text
1234 5678 9012 3456 7890
```

---

# 28. سجل التدقيق

يمكن استخدام:

```python
mail.thread
mail.activity.mixin
```

مع نموذج سجل إضافي:

```python
utility.prepaid.audit.log
```

يسجل:

* إنشاء الطلب.
* إعادة التسعير.
* تعديل المبلغ.
* تأكيد الدفع.
* إرسال طلب STS.
* استجابة المزود.
* إعادة المحاولة.
* عرض التوكن.
* إعادة الطباعة.
* إرسال التوكن.
* طلب العكس.
* اعتماد التسوية.
* تنفيذ الاسترداد.
* المستخدم.
* الفرع.
* القناة.
* عنوان IP عند توفره.

---

# 29. الخدمات الداخلية

رغم وجود موديول واحد، يجب عدم وضع جميع الأعمال داخل Models ضخمة.

## الخدمات المقترحة

```text
VendingEngine
TariffAdapter
STSGateway
DebtRecoveryEngine
PrepaidAccountingEngine
ReversalEngine
NotificationEngine
ReconciliationEngine
IdempotencyService
PrepaidSecurityService
```

## مثال

```python
class VendingEngine:

    def create_quote(self, values):
        pass

    def create_vending_request(self, quote, payment_data):
        pass

    def confirm_payment(self, request):
        pass

    def submit_to_sts(self, request):
        pass

    def complete_vending(self, request, provider_result):
        pass

    def fail_vending(self, request, error):
        pass
```

هذا يمنع تداخل مسؤوليات:

* POS.
* المحاسبة.
* STS.
* التعرفة.
* الإشعارات.

---

# 30. التسلسل النهائي للعملية

```text
Customer Selects Account
        ↓
Enter Recharge Amount
        ↓
utility_prepaid Calculates Quote
        ↓
Display Fees, Debt and kWh
        ↓
Create Vending Request
        ↓
Collect Payment through POS
        ↓
Confirm Payment
        ↓
Commit Request
        ↓
Send STS Job
        ↓
STS Provider Generates Token
        ↓
Store Token
        ↓
Create Utility Transaction
        ↓
Create Accounting Entries
        ↓
Update Customer Account Statistics
        ↓
Print Receipt
        ↓
Send SMS / Portal Notification
        ↓
Complete Vending Request
```

---

# 31. النتيجة المعمارية

بهذا التصميم يكون `utility_prepaid` موديولاً واحداً متكاملاً يحتوي على جميع وظائف الدفع المسبق، مع المحافظة على:

* فصل المسؤوليات داخل الكود.
* سهولة التثبيت والنشر.
* عدم الحاجة إلى تثبيت موديولات إضافية.
* دعم POS والبوابة وAPI من نفس الموديول.
* دعم عدة مزودي STS.
* دعم AMI المتعلق بالدفع المسبق.
* تكامل المحاسبة والورديات.
* قابلية التوسع.
* سهولة الصيانة.
* حماية من التكرار.
* توافق مع Odoo 16.
* عدم وضع منطق الأعمال داخل JavaScript أو `pos.order`.
* عدم تخزين مفاتيح التشفير الحساسة داخل Odoo.

يظل `utility_core` مسؤولاً فقط عن البيانات العامة المشتركة، مثل:

* المشتركين.
* حسابات الخدمة.
* العقود.
* العدادات.
* المناطق.
* التعرفات الأساسية.
* هيكل الشبكة.

أما كل ما يتعلق ببيع الكهرباء مسبقة الدفع وتوليد التوكن والتحصيل والتسويات والاسترداد، فيكون داخل:

```text
utility_prepaid
```
