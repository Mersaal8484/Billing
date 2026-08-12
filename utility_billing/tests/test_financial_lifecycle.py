from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_financial')
class TestFinancialLifecycle(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.partner = self.env['res.partner'].create({
            'name': 'مشترك دورة مالية كاملة',
        })
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'سكني مالية',
            'code': 'RES_FIN_LIFE',
        })
        self.sub_type = self.env['utility.subscriber'].create({
            'name': 'سكني عام مالية',
            'code': 'RES_GEN_FIN',
            'category_id': self.category.id,
        })
        self.template = self.env['utility.contract.template'].create({
            'name': 'قالب عقد مالية',
            'code': 'TPL_FIN_LIFE',
            'subscriber_category_id': self.category.id,
            'subscriber_id': self.sub_type.id,
        })
        self.customer = self.env['utility.customer'].create({
            'name': 'حساب المشترك الدورة المالية',
            'customer_number': 'CUST-FIN-001',
            'partner_id': self.partner.id,
            'subscriber_category_id': self.category.id,
            'subscriber_id': self.sub_type.id,
            'contract_template_id': self.template.id,
        })
        self.date_range_type = self.env['date.range.type'].create({
            'name': 'فترة قراءات مالية',
            'billing_period': True,
        })
        self.date_range = self.env['date.range'].create({
            'name': 'مارس 2026 - مالية',
            'type_id': self.date_range_type.id,
            'date_start': '2026-03-01',
            'date_end': '2026-03-31',
            'period_role': 'reading',
            'state': 'open',
        })
        self.payment_period = self.env['date.range'].create({
            'name': 'سداد مارس 2026 - مالية',
            'type_id': self.date_range_type.id,
            'date_start': '2026-03-01',
            'date_end': '2026-04-15',
            'period_role': 'payment',
            'reading_period_id': self.date_range.id,
            'state': 'open',
        })
        self.product = self.env['product.product'].create({
            'name': 'خدمة استهلاك كهرباء - مالية',
            'type': 'service',
        })
        self.journal = self.env['account.journal'].create({
            'name': 'يومية البنك الرئيسي',
            'code': 'BNK01',
            'type': 'bank',
            'company_id': self.company.id,
        })

    def test_full_accounting_lifecycle_sign_convention(self):
        """Test accounting_balance signs across Invoice (+500), Partial Payment (-200), Credit Note (-100), Final Payment (-200)."""
        # Initial balance = 0
        self.customer._compute_accounting_balance()
        self.assertEqual(self.customer.accounting_balance, 0.0)

        # 1. Issue Invoice (+500)
        order = self.env['sale.order'].create({
            'customer_id': self.customer.id,
            'partner_id': self.partner.id,
            'date_range_id': self.date_range.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 500.0,
            })],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        invoice.action_post()

        self.customer._compute_accounting_balance()
        self.assertAlmostEqual(self.customer.accounting_balance, 500.0, places=2)

        # 2. Partial Payment (-200) -> Balance = 300
        payment1 = self.env['account.payment'].create({
            'partner_id': self.partner.id,
            'amount': 200.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'journal_id': self.journal.id,
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'utility_payment_method': 'bank',
            'date': self.date_range.date_start,
        })
        payment1.action_post()

        self.customer._compute_accounting_balance()
        self.assertAlmostEqual(self.customer.accounting_balance, 300.0, places=2)

        # 3. Credit Note (-100) -> Balance = 200
        credit_note_wizard = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=invoice.ids
        ).create({
            'refund_method': 'refund',
            'reason': 'تعديل خصم إشعار دائن',
            'journal_id': invoice.journal_id.id,
        })
        res = credit_note_wizard.reverse_moves()
        credit_note = self.env['account.move'].browse(res['res_id'])
        credit_note.action_post()

        self.customer._compute_accounting_balance()
        self.assertAlmostEqual(self.customer.accounting_balance, 200.0, places=2)

        # 4. Final Payment (-200) -> Balance = 0
        payment2 = self.env['account.payment'].create({
            'partner_id': self.partner.id,
            'amount': 200.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'journal_id': self.journal.id,
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'utility_payment_method': 'bank',
            'date': self.date_range.date_start,
        })
        payment2.action_post()

        self.customer._compute_accounting_balance()
        self.assertAlmostEqual(self.customer.accounting_balance, 0.0, places=2)
