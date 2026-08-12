from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_concurrency')
class TestPaymentConcurrency(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.partner = self.env['res.partner'].create({
            'name': 'اختبار التزامن الخالي من التداخل',
        })
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'سكني تزامن موثوق',
            'code': 'RES_CONC_REAL',
        })
        self.sub_type = self.env['utility.subscriber'].create({
            'name': 'سكني عام تزامن موثوق',
            'code': 'RES_GEN_CONC_REAL',
            'category_id': self.category.id,
        })
        self.template = self.env['utility.contract.template'].create({
            'name': 'قالب عقد تزامن موثوق',
            'code': 'TPL_CONC_REAL',
            'subscriber_category_id': self.category.id,
            'subscriber_id': self.sub_type.id,
        })
        self.customer = self.env['utility.customer'].create({
            'name': 'حساب المشترك التزامني الموثوق',
            'customer_number': 'CUST-CONC-REAL-001',
            'partner_id': self.partner.id,
            'subscriber_category_id': self.category.id,
            'subscriber_id': self.sub_type.id,
            'contract_template_id': self.template.id,
        })
        self.date_range_type = self.env['date.range.type'].create({
            'name': 'فترة قراءات تزامن موثوق',
            'billing_period': True,
            'fiscal_year': False,
        })
        self.date_range = self.env['date.range'].create({
            'name': 'يناير 2026 - تزامن موثوق',
            'type_id': self.date_range_type.id,
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
            'period_role': 'reading',
            'state': 'open',
        })
        self.payment_period = self.env['date.range'].create({
            'name': 'سداد يناير 2026 - تزامن موثوق',
            'type_id': self.date_range_type.id,
            'date_start': '2026-01-01',
            'date_end': '2026-02-15',
            'period_role': 'payment',
            'reading_period_id': self.date_range.id,
            'state': 'open',
        })
        self.product = self.env['product.product'].create({
            'name': 'طاقة كهربائية - تزامن موثوق',
            'type': 'service',
        })
        self.order = self.env['sale.order'].create({
            'customer_id': self.customer.id,
            'partner_id': self.partner.id,
            'date_range_id': self.date_range.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 500.0,
            })],
        })
        self.order.action_confirm()
        self.invoice = self.order._create_invoices()
        self.invoice.action_post()

        self.journal = self.env['account.journal'].create({
            'name': 'محفظة الدفع الإلكتروني',
            'code': 'GW02',
            'type': 'bank',
            'company_id': self.env.company.id,
        })
        self.provider = self.env['utility.integration.provider'].create({
            'name': 'مزود دفع إلكتروني',
            'code': 'GW_PROVIDER_02',
            'provider_type': 'payment_gateway',
            'is_payment_capable': True,
            'payment_direction': 'inbound',
            'payment_journal_id': self.journal.id,
            'active': True,
        })

    def test_concurrent_manual_vs_gateway_payment_race(self):
        """Test racing manual payment vs gateway payment against same invoice residual."""
        self.assertEqual(self.invoice.amount_residual, 500.0)

        # Create a pending gateway transaction for 300
        tx = self.env['utility.payment.gateway.transaction'].create({
            'provider_id': self.provider.id,
            'payment_direction': 'inbound',
            'sale_order_id': self.order.id,
            'utility_invoice_id': self.invoice.id,
            'amount': 300.0,
            'state': 'pending',
        })

        # Concurrent manual payment of 400 posted first (residual becomes 100)
        staff = self.env['utility.staff'].search([
            ('company_id', '=', self.company.id),
            ('user_role_id.code', '=', 'collector'),
        ], limit=1)
        if not staff:
            role = self.env['utility.staff.role'].create({'name': 'متحصل', 'code': 'collector'})
            staff = self.env['utility.staff'].create({
                'name': 'متحصل اختبار',
                'user_id': self.env.uid,
                'user_role_id': role.id,
                'collection_journal_id': self.journal.id,
            })

        manual_payment = self.env['account.payment'].create({
            'partner_id': self.partner.id,
            'amount': 400.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'journal_id': self.journal.id,
            'utility_sale_order_id': self.order.id,
            'utility_invoice_id': self.invoice.id,
            'utility_payment_method': 'bank',
            'date': self.date_range.date_start,
        })
        manual_payment.action_post()

        # Invalidate invoice cache to reflect new residual of 100
        self.invoice.invalidate_recordset()
        self.assertEqual(self.invoice.amount_residual, 100.0)

        # Now attempt to confirm gateway transaction for 300 -> MUST fail validation
        with self.assertRaises(ValidationError):
            tx.action_confirm_payment(provider_reference='REF-RACE-001')

        self.assertNotEqual(tx.state, 'done')
        self.assertEqual(self.invoice.amount_residual, 100.0)

    def test_multi_cursor_sequential_residual_lock(self):
        """Test multi-cursor residual locking and transaction serialization."""
        new_cr = self.env.registry.cursor()
        try:
            env2 = self.env(cr=new_cr)
            # Transaction 1 posts 300.0
            tx1 = self.env['utility.payment.gateway.transaction'].create({
                'provider_id': self.provider.id,
                'payment_direction': 'inbound',
                'sale_order_id': self.order.id,
                'utility_invoice_id': self.invoice.id,
                'amount': 300.0,
                'state': 'pending',
            })
            tx1.action_confirm_payment(provider_reference='REF-MULTI-1')

            # In Cursor 2 (simulating concurrent worker), check invoice residual after lock release
            inv2 = env2['account.move'].browse(self.invoice.id)
            inv2.invalidate_recordset()
            self.assertEqual(inv2.amount_residual, 200.0)
        finally:
            new_cr.close()
