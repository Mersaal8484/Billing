# مراجعة حقول Float المرشحة للتحويل إلى Monetary

تاريخ المراجعة: 2026-07-06

النطاق: فحص ملفات Python داخل موديلات `utility_core`, `utility_billing`, `utility_prepaid`, `utility_operations`, `utility_inventory`, و `utility_portal`.

## خلاصة تنفيذية

يوجد عدد جيد من الحقول المالية ما زالت معرفة كـ `fields.Float` رغم أنها تمثل مبالغ، أرصدة، رسوم، غرامات، أو أسعار. الأفضل تحويلها إلى `fields.Monetary` حتى تستفيد من دقة العملة، عرض العملة في الواجهات، واتساق التقارير والمحاسبة.

الأولوية الأعلى للتحويل هي حقول الفواتير والتحصيل والتسويات والغرامات والودائع لأنها تدخل مباشرة في عمليات محاسبية أو دفع.

## قاعدة التحويل المقترحة

- إذا كان الموديل يرث من `sale.order` أو مرتبطا مباشرة به، استخدم `currency_id` الموجود في أمر البيع.
- إذا كان الموديل يحتوي `company_id` فقط، أضف:

```python
currency_id = fields.Many2one(
    'res.currency',
    related='company_id.currency_id',
    string='العملة',
    store=True,
    readonly=True,
)
```

- إذا كان الموديل مرتبطا بفاتورة/أمر بيع، الأفضل جعل العملة `related='sale_order_id.currency_id'`.
- حقول السعر لكل kWh يمكن تحويلها إلى `Monetary` إذا كانت دقة العملة كافية. إذا كان السعر يحتاج أكثر من دقة العملة، أبقها `Float` مع `digits='Product Price'` أو دقة مخصصة.

## أولوية عالية: مبالغ مالية مباشرة

| الملف | الحقول | السبب | العملة المقترحة |
|---|---|---|---|
| `utility_billing/models/utility_sale_order.py` | `amount_energy`, `amount_service`, `amount_discount`, `amount_local_fee`, `amount_penalty`, `amount_paid`, `balance_due`, `previous_balance`, `total_due_amount` | كلها مبالغ فاتورة أو أرصدة مالية مرتبطة بـ `sale.order`. | استخدام `currency_id` القياسي في `sale.order`. |
| `utility_billing/models/utility_deposit.py` | `amount` | مبلغ تأمين يدخل في `account.payment` و `account.move`. | إضافة `currency_id` من `company_id.currency_id` أو ربطها بعملة الشركة. |
| `utility_billing/models/utility_penalty.py` | `amount` | مبلغ غرامة يتحول إلى فاتورة محاسبية `account.move`. | الأفضل `related='sale_order_id.currency_id'` مع fallback لعملة الشركة إذا لم توجد فاتورة. |
| `utility_billing/models/utility_financial_settlement.py` | `amount` | مبلغ تسوية مالية يولد قيود محاسبية. | إضافة `currency_id` من `company_id.currency_id`، ويتطلب إضافة `company_id` إن لم يكن موجودا. |
| `utility_billing/models/utility_writeoff.py` | `amount` | مبلغ إعفاء/إثبات مرتبط بالفاتورة وبإشعار دائن. | الأفضل `related='sale_order_id.currency_id'`. |
| `utility_billing/models/utility_installment_plan.py` | `amount_total`, `paid_amount`, `remaining_amount`, `utility.installment.plan.line.amount`, `utility.installment.plan.line.paid_amount`, `utility.installment.plan.line.remaining_amount` | مبالغ خطة تقسيط وأقساط محسوبة من رصيد فاتورة. | `related='sale_order_id.currency_id'` في الخطة، و `related='plan_id.currency_id'` في السطور. |
| `utility_billing/models/utility_billing_cycle.py` | `total_amount` | إجمالي مبالغ فواتير فترة. | حقل العملة غير مباشر لأن الموديل هو `date.range`; يحتاج قرارا: عملة الشركة أو فصل الإجمالي حسب الشركة/العملة. |
| `utility_portal/models/utility_payment_gateway_transaction.py` | `amount` | مبلغ معاملة بوابة الدفع، والموديل يحتوي `currency_id` بالفعل. | تحويل مباشر إلى `fields.Monetary(currency_field='currency_id')`. |
| `utility_core/models/utility_customer.py` | `balance`, `emergency_credit`, `credit_limit`, `total_purchases` | أرصدة وحدود ائتمانية ومشتريات، والواجهة تعرضها حاليا كـ monetary widget. | استخدام `company_currency_id` الموجود بالفعل. |
| `utility_core/models/utility_settings.py` | `emergency_credit_amount`, `low_credit_threshold` | قيم إعدادات مالية لرصيد الطوارئ وحد الرصيد المنخفض. | يمكن إبقاؤها `Float` بسبب `config_parameter`، لكن الأفضل وظيفيا استخدام `Monetary` مع `currency_id` متعلق بعملة الشركة إن كانت ستعرض كعملة. |

## أولوية متوسطة: أسعار وتعرفة ورسوم لكل وحدة

هذه الحقول تمثل أسعارا أو رسوما، لكنها قد تحتاج دقة أعلى من دقة العملة بسبب التسعير لكل kWh. التحويل إلى `Monetary` صحيح من ناحية الدلالة المالية، لكن يجب التأكد من سياسة التقريب.

| الملف | الحقول | التوصية |
|---|---|---|
| `utility_core/models/utility_contract_template.py` | `price_per_kwh`, `service_charge`, `fixed_charge`, `min_charge`, `max_charge`, `local_fee_per_kwh`, `local_fee_mu_allim`, `local_fee_cleaning`, `discount_unit_value` | أضف `currency_id` متعلق بعملة الشركة. حول الرسوم الثابتة والحدود إلى `Monetary`. أسعار "لكل kWh" تحول فقط إذا كانت دقة العملة كافية. |
| `utility_core/models/utility_contract_template.py` | `utility.contract.template.line.specific_price` | سعر محدد لبند عقد، مرشح قوي لـ `Monetary`. |
| `utility_core/models/utility_contract_template_block.py` | `price_per_kwh` | سعر شريحة لكل kWh؛ نفس ملاحظة الدقة. العملة يمكن أن تكون `related='template_id.currency_id'`. |
| `utility_core/models/utility_contract_template_history.py` | `old_price`, `new_price`, `old_service_charge`, `new_service_charge` | سجل أسعار ورسوم؛ يجب أن يتبع عملة القالب `template_id.currency_id`. |
| `utility_core/models/utility_subscriber.py` | `subsidized_price_per_kwh` | سعر وحدة مدعومة؛ مالي لكن يحتاج قرار دقة. |
| `utility_prepaid/models/utility_pos_order.py` | `unit_price` | سعر وحدة kWh في أمر POS؛ مالي ويفضل `Monetary` إذا لم تكن هناك حاجة لأكثر من دقة العملة. |

## حقول Float صحيحة ولا ينصح بتحويلها

هذه الحقول قياسات، كميات، قراءات، نسب، ساعات، أو حدود تشغيلية وليست مبالغ مالية:

- قراءات واستهلاك: `previous_reading`, `current_reading`, `reading_value`, `consumption`, `last_reading_value`, `last_invoice_reading`, حقول التسويات القرائية، وقراءات تبديل العداد.
- kWh وكميات الطاقة: `kwh`, `kwh_purchased`, `total_kwh_purchased`, `supplied_kwh`, `from_kwh`, `to_kwh`, `discount_first_units`, `subsidized_max_units`.
- كميات المخزون: `quantity`, `min_quantity`, `expected_quantity`, `counted_quantity`, `difference` في `utility_inventory`.
- قياسات كهربائية وتشغيلية: `voltage`, `current`, `power`, `capacity`, `capacity_kva`, `rated_capacity`, `current_load`, `load_percentage`, `voltage_primary`, `voltage_secondary`.
- نسب وحدود: `late_penalty_percentage`, `loss_percentage`, `show_loss_threshold`, `max_transformer_loss_tolerance`, `consumption_variation_alert_percentage`, `subsidized_percentage`.
- وقت وساعات: `time_from`, `time_to`, `labor_hours`.

## ملاحظات تطبيقية قبل الإصلاح

1. تحويل نوع الحقل من `Float` إلى `Monetary` في Odoo يغير تعريف العمود من ناحية ORM لا نوع PostgreSQL غالبا، لكنه يتطلب تحديث الموديول وإضافة حقل العملة للواجهات عند الحاجة.
2. أي حقل محسوب محفوظ `store=True` يجب مراجعة `@api.depends` بعد إضافة العملة، خصوصا في التقسيط والفواتير.
3. الحقول المرتبطة بالمحاسبة يجب أن تستخدم نفس عملة المستند المحاسبي لا عملة الشركة دائما. مثال: فاتورة البيع تستخدم `sale.order.currency_id`.
4. لا تحول حقول السعر لكل kWh بشكل آلي قبل تحديد دقة التعرفة. بعض شركات الكهرباء تحتاج 4 إلى 6 خانات عشرية في سعر الوحدة، بينما `Monetary` يتبع دقة العملة غالبا.
5. عند تعديل الواجهات، استخدم `widget="monetary"` و `options="{'currency_field': 'currency_id'}"` فقط عند الحاجة؛ حقول `Monetary` تعرض العملة بشكل طبيعي إذا عرف `currency_field`.

## ترتيب إصلاح مقترح

1. ابدأ بـ `utility_portal.models.utility_payment_gateway_transaction.amount` لأنه يملك `currency_id` جاهزا والتحويل منخفض المخاطر.
2. حول حقول `sale.order` المالية في `utility_billing/models/utility_sale_order.py` لأنها تعتمد على `currency_id` موجود.
3. حول نماذج العمليات المالية المنفصلة: الودائع، الغرامات، التسويات، الإعفاءات، والتقسيط.
4. حول أرصدة المشترك في `utility.customer` باستخدام `company_currency_id`.
5. ناقش أو ثبت سياسة دقة أسعار التعرفة قبل تحويل حقول أسعار kWh في قوالب العقود والشرائح.
