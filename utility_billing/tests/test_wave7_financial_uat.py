from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestWave7FinancialUAT(TransactionCase):
    """Deterministic financial UAT for invoice, payment, and allocation invariants."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.Customer = cls.env['utility.customer']
        cls.Category = cls.env['utility.subscriber.category']
        cls.Subscriber = cls.env['utility.subscriber']
        cls.Account = cls.env['account.account']
        cls.Product = cls.env['product.product']
        cls.Move = cls.env['account.move']
        cls.Payment = cls.env['account.payment']

        cls.category = cls.Category.create({
            'name': 'فئة UAT المالي Wave 7',
            'code': 'W7-UAT-CAT',
        })
        cls.subscriber = cls.Subscriber.create({
            'name': 'نوع UAT المالي Wave 7',
            'code': 'W7-UAT-SUB',
            'category_id': cls.category.id,
        })
        cls.income = cls.Account.search([
            ('company_id', '=', cls.env.company.id),
            ('account_type', '=', 'income'),
        ], limit=1)
        cls.sale_journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.env.company.id),
            ('type', '=', 'sale'),
        ], limit=1)
        cls.bank_journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.env.company.id),
            ('type', '=', 'bank'),
        ], limit=1)
        if not cls.income or not cls.sale_journal or not cls.bank_journal:
            raise ValidationError('بيئة UAT تحتاج حساب دخل ويومية مبيعات وبنك.')

        cls.product = cls.Product.create({
            'name': 'منتج UAT مالي Wave 7',
            'type': 'service',
        })
        cls.product.property_account_income_id = cls.income

        range_type = cls.env['date.range.type'].search([
            ('default_billing_period', '=', 'monthly'),
            ('fiscal_year', '=', False),
        ], limit=1)
        if not range_type:
            range_type = cls.env['date.range.type'].create({
                'name': 'نوع فترة UAT Wave 7',
                'default_billing_period': 'monthly',
                'allow_overlap': True,
            })
        cls.reading_period = cls.env['date.range'].create({
            'name': 'فترة قراءة UAT Wave 7',
            'period_code': 'W7-UAT-READING',
            'cycle_key': 'W7-UAT-READING',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'type_id': range_type.id,
            'date_start': '2099-01-01',
            'date_end': '2099-01-31',
            'state': 'open',
        })
        cls.payment_period = cls.env['date.range'].create({
            'name': 'فترة دفع UAT Wave 7',
            'period_code': 'W7-UAT-PAYMENT',
            'cycle_key': 'W7-UAT-PAYMENT',
            'period_role': 'payment',
            'billing_cadence': 'monthly',
            'reading_period_id': cls.reading_period.id,
            'date_start': '2099-02-01',
            'date_end': '2099-02-28',
            'state': 'open',
        })

    def _create_invoice(self):
        partner = self.Partner.create({'name': 'عميل UAT المالي Wave 7'})
        customer = self.Customer.create({
            'customer_number': 'W7-UAT-CUSTOMER',
            'partner_id': partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'customer_id': customer.id,
            'date_range_id': self.reading_period.id,
            'period_start': self.reading_period.date_start,
            'period_end': self.reading_period.date_end,
        })
        invoice = self.Move.create({
            'move_type': 'out_invoice',
            'journal_id': self.sale_journal.id,
            'partner_id': partner.id,
            'utility_customer_id': customer.id,
            'utility_sale_order_id': order.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': 'UAT استهلاك كهرباء',
                'quantity': 1.0,
                'price_unit': 1000.0,
                'account_id': self.income.id,
            })],
        })
        invoice.action_post()
        return customer, order, invoice

    def _create_payment(self, order, invoice, amount, reference):
        payment = self.Payment.create({
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'partner_id': order.partner_id.id,
            'amount': amount,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'utility_payment_method': 'bank',
            'journal_id': self.bank_journal.id,
            'date_range_id': self.payment_period.id,
            'date': date(2099, 2, 10),
            'electronic_doc_no': reference,
        })
        payment.action_post()
        return payment

    def test_partial_payments_preserve_accounting_residual(self):
        _customer, order, invoice = self._create_invoice()
        first = self._create_payment(order, invoice, 600.0, 'W7-UAT-P1')
        invoice.invalidate_recordset()
        self.assertEqual(first.state, 'posted')
        self.assertAlmostEqual(invoice.amount_residual, 400.0, places=2)
        self.assertEqual(first.allocation_count, 1)
        self.assertAlmostEqual(
            first.allocation_ids.allocated_amount, 600.0, places=2)
        self.assertTrue(first.allocation_ids.partial_reconcile_ids)

        second = self._create_payment(order, invoice, 400.0, 'W7-UAT-P2')
        invoice.invalidate_recordset()
        self.assertEqual(second.state, 'posted')
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)
        self.assertEqual(second.allocation_count, 1)
        # Bank journals may remain ``in_payment`` until the bank statement
        # clears the outstanding account; the receivable invariant is already
        # proven by the zero residual and exact partial reconciliations.
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))

    def test_overpayment_is_rejected_before_accounting_post(self):
        _customer, order, invoice = self._create_invoice()
        self._create_payment(order, invoice, 600.0, 'W7-UAT-P3')
        with self.assertRaises(ValidationError):
            self._create_payment(order, invoice, 500.0, 'W7-UAT-P4')
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 400.0, places=2)
