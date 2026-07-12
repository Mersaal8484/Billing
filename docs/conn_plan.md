# التصحيح المعماري لإدارة رسوم أوامر الخدمة دون محافظ عملاء

## 1. القرار المعماري

لا يحتوي النظام على محفظة مالية للعملاء، ولذلك يجب استبعاد جميع وظائف المحفظة من تصميم أوامر الخدمة.

تكون طرق تحصيل رسوم الخدمة المعتمدة:

```text
No Charge
Customer Invoice
Direct Payment
Add to Postpaid Bill
```

أما عملاء العدادات مسبقة الدفع، فيتم التعامل معهم من خلال:

```text
POS Sale / Payment Transaction
→ Payment Confirmation
→ STS Token Generation
```

ولا يتم إنشاء رصيد محفظة أو خصم رسوم الخدمة من رصيد داخلي للعميل.

---

# 2. إزالة النماذج والحقول المرتبطة بالمحفظة

يجب إزالة أو عدم استخدام العناصر التالية في سياق أوامر الخدمة:

```python
prepaid_transaction_id
wallet_transaction_ids
action_deduct_from_wallet()
action_deduct_from_prepaid_balance()
prepaid_balance
balance_before
balance_after
financial_clearance_from_wallet
```

كما يجب حذف طريقة الفوترة التالية:

```python
('prepaid_balance', 'Prepaid Balance Deduction')
```

ولا يتم إنشاء معاملة رصيد عند تحصيل رسوم:

* التوصيل.
* الفصل.
* إعادة التوصيل.
* الفحص.
* استبدال العداد.
* الصيانة.

---

# 3. طرق المعالجة المالية الصحيحة

## الطريقة الأولى: خدمة مجانية

تستخدم عندما تكون الخدمة غير قابلة للفوترة.

```text
Billing Method = No Charge
Financial State = Not Required
```

لا يتم إنشاء فاتورة أو دفعة.

---

## الطريقة الثانية: فاتورة عميل مستقلة

تستخدم عندما يجب إصدار فاتورة مستقلة لرسوم الخدمة.

```text
Service Order
→ Service Charge
→ Customer Invoice
→ Payment
→ Financial Clearance
→ Execution
```

أمثلة:

* رسوم التوصيلة الجديدة.
* رسوم إعادة التوصيل.
* رسوم استبدال العداد.
* رسوم الفحص.
* رسوم المسح الميداني.

يتم إنشاء الفاتورة باستخدام:

```text
account.move
```

من النوع:

```python
move_type = 'out_invoice'
```

---

## الطريقة الثالثة: الدفع المباشر

تستخدم عندما يدفع العميل الرسوم مباشرة لدى أمين الصندوق أو نقطة التحصيل.

```text
Service Order
→ Payment Request
→ Payment Collection
→ Accounting Entry / Receipt
→ Financial Clearance
→ Execution
```

يجب أن يتم الدفع المباشر من خلال أدوات Odoo المالية القياسية، مثل:

```text
account.payment
account.move
POS Order
Cashier Shift
Collection Journal
```

ولا يتم تسجيل قيمة الدفع مباشرة داخل أمر الخدمة دون مستند مالي.

---

## الطريقة الرابعة: إضافة الرسم إلى فاتورة الاستهلاك

تستخدم مع العملاء الآجلين عندما تقرر المؤسسة إضافة رسوم الخدمة إلى دورة الفوترة القادمة.

```text
Service Order
→ Deferred Service Charge
→ Next Consumption Bill
→ Customer Invoice
→ Payment
```

يمكن تنفيذ ذلك من خلال نموذج:

```text
utility.billing.charge
```

أو من خلال سجل رسوم خدمة ينتظر دورة الفوترة التالية.

يجب أن يبقى الرسم مرتبطاً بأمر الخدمة الأصلي.

---

# 4. تصميم العدادات مسبقة الدفع

## بيع الكهرباء مسبقة الدفع

تكون الدورة الصحيحة:

```text
Customer Selects Recharge Amount
→ POS Order or Payment Transaction
→ Payment Confirmed
→ STS Token Requested
→ Token Generated
→ Token Delivered
```

لا توجد خطوة:

```text
Deposit into Customer Wallet
```

ولا توجد خطوة:

```text
Deduct Token Amount from Wallet
```

لأن دفع العميل نفسه هو مصدر تمويل عملية إصدار التوكن.

---

# 5. رسوم الخدمات لعملاء الدفع المسبق

كون العميل يستخدم عداداً مسبق الدفع لا يعني أن رسوم الخدمة تخصم من رصيد الكهرباء داخل العداد.

رسوم مثل إعادة التوصيل أو استبدال العداد يجب تحصيلها من خلال أحد المسارات التالية:

```text
Separate Customer Invoice
Direct Cash / Bank / POS Payment
Add Fee as Separate POS Product
```

## المسار المفضل

```text
Reconnection Service Order
→ Reconnection Fee Product
→ Invoice or POS Payment
→ Payment Confirmed
→ Financial Clearance
→ Reconnection Execution
```

لا يتم إصدار STS Token مقابل رسوم الخدمة إلا إذا كانت الرسوم جزءاً صريحاً من عملية شحن الكهرباء وتم فصل قيمتها محاسبياً عن قيمة الطاقة المباعة.

---

# 6. تعديل حقل طريقة الفوترة

يكون الحقل بالشكل التالي:

```python
billing_method = fields.Selection([
    ('none', 'No Charge'),
    ('invoice', 'Customer Invoice'),
    ('direct_payment', 'Direct Payment'),
    ('next_bill', 'Add to Next Postpaid Bill'),
], string='Billing Method', default='none', tracking=True)
```

إذا كان خيار إضافة الرسم إلى فاتورة الاستهلاك غير مطلوب حالياً، يمكن تبسيطه إلى:

```python
billing_method = fields.Selection([
    ('none', 'No Charge'),
    ('invoice', 'Customer Invoice'),
    ('direct_payment', 'Direct Payment'),
], string='Billing Method', default='none', tracking=True)
```

---

# 7. حالة التسوية المالية

يجب أن تعكس الحالة مستندات الفوترة والدفع الفعلية.

```python
financial_state = fields.Selection([
    ('not_required', 'Not Required'),
    ('pending_invoice', 'Pending Invoice'),
    ('pending_payment', 'Pending Payment'),
    ('partially_paid', 'Partially Paid'),
    ('cleared', 'Cleared'),
    ('reversed', 'Reversed'),
    ('cancelled', 'Cancelled'),
], string='Financial State', compute='_compute_financial_state', store=True)
```

## مصادر الحالة

تحدد الحالة من خلال:

* الفاتورة.
* حالة الدفع.
* القيود المحاسبية.
* عملية POS.
* رسوم دورة الفوترة.
* الإشعار الدائن.

لا ينبغي أن يستطيع المستخدم تغيير التسوية المالية يدوياً.

---

# 8. نموذج رسوم الخدمة

يوصى باستخدام نموذج:

```text
utility.service.charge
```

للفصل بين أمر الخدمة والمستند المالي.

## الحقول المقترحة

```python
service_order_id
account_id
partner_id
product_id
description
quantity
price_unit
tax_ids
amount_untaxed
amount_tax
amount_total
billing_method
state
invoice_id
payment_id
pos_order_id
billing_charge_id
company_id
currency_id
```

## الحالات

```text
Draft
→ Confirmed
→ Invoiced / Payment Requested
→ Paid
→ Reversed
→ Cancelled
```

هذا النموذج ليس محفظة، بل سجل يوضح:

* لماذا استحق الرسم؟
* كم قيمته؟
* كيف تم تحصيله؟
* ما الفاتورة أو الدفعة المرتبطة؟
* هل تم عكسه؟

---

# 9. ربط أمر الخدمة بالفواتير

يفضل عدم استخدام فاتورة واحدة فقط:

```python
invoice_id
```

بل إضافة الرابط إلى `account.move`:

```python
service_order_id = fields.Many2one(
    'utility.service.order',
    index=True,
    copy=False,
    check_company=True,
)
```

وفي أمر الخدمة:

```python
invoice_ids = fields.One2many(
    'account.move',
    'service_order_id',
    string='Service Invoices',
)

invoice_count = fields.Integer(
    compute='_compute_invoice_count'
)
```

وذلك لدعم:

* الفاتورة الأصلية.
* إشعار دائن.
* فاتورة تصحيح.
* فاتورة فرق.

---

# 10. مسار التوصيلة الجديدة

```text
New Connection Request
→ Administrative Approval
→ Meter and Material Availability Check
→ Connection Fee Calculation
→ Invoice or Direct Payment
→ Payment Confirmation
→ Financial Clearance
→ Work Order
→ Meter Installation
→ Stock Picking Completion
→ Initial Reading and Seals
→ Account Activation
→ Order Completion
```

---

# 11. مسار إعادة التوصيل

```text
Outstanding Debt Settlement
→ Reconnection Request
→ Previous Disconnection Order Validation
→ Reconnection Fee Calculation
→ Invoice or Direct Payment
→ Payment Confirmation
→ Financial Clearance
→ Reconnection Work Order
→ Reading and Seal Registration
→ Meter Activation
→ Customer Account Activation
→ Order Completion
```

يشترط تحقق شرطين منفصلين:

```text
Outstanding Debt Cleared
AND
Reconnection Fee Paid
```

---

# 12. مسار الفصل بسبب المديونية

```text
Posted Overdue Receivables
→ Grace Period Expired
→ Disconnection Eligibility Check
→ Disconnection Service Order
→ Supervisor Approval
→ Work Order Assignment
→ Debt Recheck Before Execution
→ Disconnection Execution
→ Final Reading and Seal
→ Meter and Account Suspension
→ Order Completion
```

إذا سدد العميل قبل التنفيذ:

```text
Payment Reconciled
→ Debt Rechecked
→ Execution Blocked
→ Work Order Cancelled
→ Service Order Cancelled
```

---

# 13. التكامل المحاسبي

يكون مصدر الحقيقة المالي:

```text
account.move
account.move.line
account.payment
account.partial.reconcile
account.full.reconcile
pos.order
```

ولا يعتمد النظام على أي رصيد داخلي موازٍ للمحاسبة.

## قيد فاتورة رسوم الخدمة

```text
Dr. Customer Receivable
    Cr. Service Revenue
    Cr. Tax Payable
```

## عند السداد

```text
Dr. Cash / Bank / POS Receivable
    Cr. Customer Receivable
```

## عند الإلغاء بعد الترحيل

يتم إنشاء إشعار دائن:

```text
Dr. Service Revenue
Dr. Tax Payable
    Cr. Customer Receivable
```

بحسب إعدادات Odoo والضرائب.

---

# 14. الدفع المسبق والمحاسبة

## بيع توكن الكهرباء

عند استلام دفعة من العميل:

```text
Dr. Cash / Bank / POS
    Cr. Prepaid Electricity Revenue
```

أو:

```text
Dr. Cash / Bank / POS
    Cr. Deferred Electricity Revenue
```

بحسب السياسة المحاسبية المعتمدة وطريقة الاعتراف بالإيراد.

## رسوم الخدمة

يجب فصلها عن قيمة الكهرباء:

```text
Dr. Cash / Bank / POS
    Cr. Service Revenue
```

ولا تدمج رسوم إعادة التوصيل مع قيمة التوكن دون وجود بنود منتجات مستقلة.

---

# 15. التعديلات المطلوبة على الموديولات

## `utility_core`

يحتوي على:

* حساب العميل.
* العداد.
* نقطة الخدمة.
* العقد.
* سجل العداد.
* البيانات الجغرافية.

ولا يحتوي على محفظة مالية.

## `utility_prepaid`

يحتوي على:

* تكامل POS.
* بيع الشحن.
* طلب STS.
* التوكنات.
* عمليات الإلغاء والعكس.
* ورديات أمين الصندوق.

ولا يحتوي على محفظة عميل.

## `utility_operations`

يحتوي على:

* أمر الخدمة.
* أمر العمل.
* التنفيذ الميداني.
* القراءة والأختام.
* الفحص والتلاعب.
* الربط بالمخزون.
* حالة التسوية المالية العامة.

## `utility_billing`

يحتوي على:

* فواتير الاستهلاك.
* رسوم الخدمات.
* الغرامات.
* المديونية.
* التحصيل.
* المصالحة.
* الفصل بسبب المديونية.
* إضافة الرسوم إلى الفاتورة القادمة.

---

# 16. التبعية المقترحة

```text
utility_core
    ├── utility_inventory
    ├── utility_operations
    ├── utility_prepaid
    └── utility_billing
```

ولربط أوامر الخدمة بالفوترة:

```text
utility_billing
    depends on:
        utility_core
        utility_operations
        account
        sale
```

ولربط رسوم الخدمة بالدفع عبر POS عند الحاجة:

```text
utility_prepaid
    depends on:
        utility_core
        utility_operations
        pos
        account
```

لكن لا ينبغي جعل `utility_operations` يعتمد مباشرة على `utility_prepaid`.

---

# 17. الحقول النهائية المقترحة لأمر الخدمة

```python
service_product_id
service_fee
billing_method
service_charge_ids
financial_state
financial_clearance_date
requires_financial_clearance
invoice_count
payment_count
```

ويجب إزالة:

```python
prepaid_transaction_id
wallet_transaction_ids
wallet_balance
wallet_state
```

---

# 18. الواجهة

## أزرار أمر الخدمة

```text
Approve
Create Service Charge
Create Invoice
Open Direct Payment
Add to Next Bill
Check Financial Clearance
Assign
Schedule
Start Work
Submit Field Completion
Approve Completion
Cancel
```

لا يظهر زر:

```text
Deduct from Wallet
```

ولا أي Smart Button متعلق بالمحفظة.

## Smart Buttons

```text
Invoices
Payments
POS Orders
Service Charges
Work Orders
Stock Pickings
Meter Logs
Tamper Cases
Attachments
```

---

# 19. التقارير المالية

تشمل التقارير:

* رسوم الخدمات المستحقة.
* رسوم الخدمات المفوترة.
* رسوم الخدمات المسددة.
* رسوم الخدمات غير المسددة.
* رسوم الخدمات المحصلة نقداً.
* رسوم الخدمات المحصلة عبر البنك.
* رسوم الخدمات المحصلة عبر POS.
* رسوم الخدمات المضافة إلى فواتير الاستهلاك.
* الإيرادات حسب نوع الخدمة.
* الإيرادات حسب المنطقة.
* الإيرادات حسب الفرع.
* الإشعارات الدائنة والاستردادات.

ولا تشمل:

```text
Wallet Balance
Wallet Debit
Wallet Refund
Wallet Liability
```

---

# 20. النتيجة المعمارية النهائية

يكون المسار المالي لأمر الخدمة:

```text
utility.service.order
→ utility.service.charge
→ account.move / account.payment / pos.order
→ Financial Clearance
→ utility.work.order
→ Field Execution
→ Meter and Account Update
→ utility.meter.log
```

ويكون مسار الكهرباء مسبقة الدفع:

```text
pos.order / payment
→ STS Token Request
→ Token Generation
→ Token Delivery
```

دون إنشاء أو استخدام محفظة للعميل.

بهذا التصميم تصبح المحاسبة القياسية في Odoo هي المصدر الوحيد للحركة المالية، بينما يبقى نظام الدفع المسبق مسؤولاً عن بيع التوكنات وربطها بالدفعات، وليس إدارة أرصدة مالية داخلية للعملاء.
