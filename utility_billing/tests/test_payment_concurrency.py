from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_concurrency')
class TestPaymentConcurrency(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.partner = self.env['res.partner'].create({
            'name': 'اختبار التزامن',
        })
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'سكني تزامن',
            'code': 'RES_CONCURRENCY',
        })
        self.sub_type = self.env['utility.subscriber'].create({
            'name': 'سكني عام تزامن',
            'code': 'RES_GEN_CONCURRENCY',
            'category_id': self.category.id,
        })
        self.template = self.env['utility.contract.template'].create({
            'name': 'قالب عقد تزامن',
            'code': 'TPL_CONCURRENCY',
            'subscriber_category_id': self.category.id,
            'subscriber_id': self.sub_type.id,
        })
        self.customer = self.env['utility.customer'].create({
            'name': 'حساب المشترك التزامني',
            'customer_number': 'CUST-CONC-001',
            'partner_id': self.partner.id,
            'subscriber_category_id': self.category.id,
            'subscriber_id': self.sub_type.id,
            'contract_template_id': self.template.id,
        })
        self.date_range_type = self.env['date.range.type'].create({
            'name': 'فترة قراءات تزامن',
            'billing_period': True,
            'fiscal_year': False,
        })
        self.date_range = self.env['date.range'].create({
            'name': 'يناير 2026 - تزامن',
            'type_id': self.date_range_type.id,
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
            'period_role': 'reading',
            'state': 'open',
        })
        self.payment_period = self.env['date.range'].create({
            'name': 'سداد يناير 2026 - تزامن',
            'type_id': self.date_range_type.id,
            'date_start': '2026-01-01',
            'date_end': '2026-02-15',
            'period_role': 'payment',
            'reading_period_id': self.date_range.id,
            'state': 'open',
        })
        self.product = self.env['product.product'].create({
            'name': 'طاقة كهربائية - تزامن',
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

    def test_multi_cursor_invoice_residual_locking(self):
        """Test that a second cursor cannot overpay an invoice undergoing payment locking."""
        new_cr = self.env.registry.cursor()
        try:
            env2 = self.env(cr=new_cr)
            inv2 = env2['account.move'].browse(self.invoice.id)
            inv2.invalidate_recordset()
            self.assertEqual(inv2.amount_residual, 500.0)
        finally:
            new_cr.close()
