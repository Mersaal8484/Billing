from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_idempotency')
class TestGatewayIdempotency(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'اختبار تكافؤ التكرار'})
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'سكني تكرار',
            'code': 'RES_IDEMPOTENCY',
        })
        self.sub_type = self.env['utility.subscriber'].create({
            'name': 'سكني عام تكرار',
            'code': 'RES_GEN_IDEMP',
            'category_id': self.category.id,
        })
        self.template = self.env['utility.contract.template'].create({
            'name': 'قالب عقد تكرار',
            'code': 'TPL_IDEMP',
            'subscriber_category_id': self.category.id,
            'subscriber_id': self.sub_type.id,
        })
        self.customer = self.env['utility.customer'].create({
            'name': 'حساب المشترك للتكرار',
            'customer_number': 'CUST-IDEMP-001',
            'partner_id': self.partner.id,
            'subscriber_category_id': self.category.id,
            'subscriber_id': self.sub_type.id,
            'contract_template_id': self.template.id,
        })
        self.date_range_type = self.env['date.range.type'].create({
            'name': 'فترة قراءات تكرار',
            'billing_period': True,
        })
        self.date_range = self.env['date.range'].create({
            'name': 'فبراير 2026 - تكرار',
            'type_id': self.date_range_type.id,
            'date_start': '2026-02-01',
            'date_end': '2026-02-28',
            'period_role': 'reading',
            'state': 'open',
        })
        self.payment_period = self.env['date.range'].create({
            'name': 'سداد فبراير 2026 - تكرار',
            'type_id': self.date_range_type.id,
            'date_start': '2026-02-01',
            'date_end': '2026-03-15',
            'period_role': 'payment',
            'reading_period_id': self.date_range.id,
            'state': 'open',
        })
        self.product = self.env['product.product'].create({
            'name': 'خدمة كهرباء - تكرار',
            'type': 'service',
        })
        self.order = self.env['sale.order'].create({
            'customer_id': self.customer.id,
            'partner_id': self.partner.id,
            'date_range_id': self.date_range.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 300.0,
            })],
        })
        self.order.action_confirm()
        self.invoice = self.order._create_invoices()
        self.invoice.action_post()

        self.journal = self.env['account.journal'].create({
            'name': 'بنك المحفظة الإلكترونية',
            'code': 'GW01',
            'type': 'bank',
            'company_id': self.env.company.id,
        })
        self.provider = self.env['utility.integration.provider'].create({
            'name': 'بوابة دفع اختبارية',
            'code': 'TEST_GATEWAY',
            'provider_type': 'payment_gateway',
            'is_payment_capable': True,
            'payment_direction': 'inbound',
            'payment_journal_id': self.journal.id,
            'active': True,
        })
        self.tx = self.env['utility.payment.gateway.transaction'].create({
            'provider_id': self.provider.id,
            'payment_direction': 'inbound',
            'sale_order_id': self.order.id,
            'utility_invoice_id': self.invoice.id,
            'amount': 300.0,
            'state': 'pending',
        })

    def test_duplicate_callback_idempotency(self):
        """Test that confirming a transaction twice does not duplicate account.payment records."""
        self.tx.action_confirm_payment(provider_reference='REF-GATEWAY-1001')
        self.assertEqual(self.tx.state, 'done')
        payment_id_1 = self.tx.payment_id.id
        self.assertTrue(payment_id_1)

        # Call again on done transaction
        self.tx.action_confirm_payment(provider_reference='REF-GATEWAY-1001')
        self.assertEqual(self.tx.state, 'done')
        self.assertEqual(self.tx.payment_id.id, payment_id_1)

        # Verify only 1 payment was created
        payments = self.env['account.payment'].search([('utility_sale_order_id', '=', self.order.id)])
        self.assertEqual(len(payments), 1)
