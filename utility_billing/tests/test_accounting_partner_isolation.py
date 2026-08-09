from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestUtilityAccountingPartnerIsolation(TransactionCase):
    """Regression tests for the one-account/one-accounting-partner model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Category = cls.env['utility.subscriber.category']
        cls.Subscriber = cls.env['utility.subscriber']
        cls.Customer = cls.env['utility.customer']
        cls.Partner = cls.env['res.partner']
        cls.category = cls.Category.create({
            'name': 'فئة اختبار العزل المحاسبي',
            'code': 'ACCOUNTING_ISOLATION',
        })
        cls.subscriber = cls.Subscriber.create({
            'name': 'نوع اختبار العزل المحاسبي',
            'category_id': cls.category.id,
        })

    def _create_customer(self, suffix, owner=None):
        owner = owner or self.Partner.create({'name': 'مالك اختبار %s' % suffix})
        customer = self.Customer.create({
            'customer_number': 'ACC-ISO-%s' % suffix,
            'partner_id': owner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })
        return owner, customer

    def test_accounts_get_distinct_accounting_partners(self):
        owner = self.Partner.create({'name': 'مالك حسابين للاختبار'})
        _, first = self._create_customer('001', owner)
        _, second = self._create_customer('002', owner)

        self.assertEqual(first.owner_partner_id, owner)
        self.assertEqual(second.owner_partner_id, owner)
        self.assertNotEqual(first.partner_id, second.partner_id)
        self.assertNotEqual(first.partner_id, owner)
        self.assertNotEqual(second.partner_id, owner)

    def test_owner_identity_and_opening_balance_are_not_cloned(self):
        owner = self.Partner.create({
            'name': 'مالك مع رصيد افتتاحي للاختبار',
            'open_balance': 100000.0,
        })
        _, customer = self._create_customer('009', owner)

        self.assertEqual(customer.owner_partner_id, owner)
        self.assertEqual(customer.partner_id.open_balance, 0.0)
        self.assertTrue(owner.has_utility_customer)
        action = owner.action_open_utility_customer_registration()
        self.assertEqual(action.get('res_id'), customer.id)

    def test_existing_accounting_partner_cannot_be_reused(self):
        _, first = self._create_customer('003')
        _, second = self._create_customer('004')

        with self.assertRaises(ValidationError):
            second.write({'partner_id': first.partner_id.id})

    def test_private_transformer_belongs_to_one_account(self):
        transformer = self.env['utility.transformer'].create({
            'name': 'محول خاص لاختبار الملكية',
            'code': 'PRV-ISO-001',
            'is_private': True,
        })
        _, first = self._create_customer('PRIVATE-001')
        first.write({'transformer_id': transformer.id})
        _, second = self._create_customer('PRIVATE-002')
        with self.assertRaises(ValidationError):
            second.write({'transformer_id': transformer.id})

    def test_balances_are_isolated_by_account_partner(self):
        _, first = self._create_customer('005')
        _, second = self._create_customer('006')
        journal = self.env['account.journal'].search([
            ('company_id', '=', self.env.company.id),
            ('type', '=', 'general'),
        ], limit=1)
        receivable = self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)
        income = self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('account_type', '=', 'income'),
        ], limit=1)
        if not journal or not receivable or not income:
            self.skipTest('Accounting demo accounts are not available.')

        for customer, amount in ((first, 100.0), (second, 250.0)):
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'line_ids': [
                    (0, 0, {
                        'name': 'اختبار رصيد كهرباء',
                        'account_id': receivable.id,
                        'partner_id': customer.partner_id.id,
                        'debit': amount,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'name': 'اختبار إيراد كهرباء',
                        'account_id': income.id,
                        'credit': amount,
                        'debit': 0.0,
                    }),
                ],
            })
            move.action_post()

        first._compute_accounting_balance()
        second._compute_accounting_balance()
        self.assertAlmostEqual(first.accounting_balance, 100.0, places=2)
        self.assertAlmostEqual(second.accounting_balance, 250.0, places=2)

    def test_sale_order_invoice_and_payment_reject_cross_account_partner(self):
        _, first = self._create_customer('007')
        _, second = self._create_customer('008')
        period = self.env['date.range'].search([], limit=1)
        if not period:
            self.skipTest('A date range is required to create a sale order.')

        order = self.env['sale.order'].create({
            'customer_id': first.id,
            'partner_id': first.partner_id.id,
            'date_range_id': period.id,
        })

        with self.assertRaises(ValidationError):
            self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': second.partner_id.id,
                'utility_sale_order_id': order.id,
            })

        journal = self.env['account.journal'].search([
            ('company_id', '=', self.env.company.id),
            ('type', '=', 'cash'),
        ], limit=1)
        if journal:
            with self.assertRaises(ValidationError):
                self.env['account.payment'].create({
                    'partner_id': second.partner_id.id,
                    'amount': 10.0,
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'journal_id': journal.id,
                    'utility_sale_order_id': order.id,
                })

            # A utility payment must name its exact invoice. The old
            # partner-wide fallback could otherwise reconcile unrelated
            # receivables belonging to the same owner.
            with self.assertRaises(ValidationError):
                self.env['account.payment'].create({
                    'partner_id': first.partner_id.id,
                    'amount': 10.0,
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'journal_id': journal.id,
                    'utility_sale_order_id': order.id,
                })
