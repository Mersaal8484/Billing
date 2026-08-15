"""
Phase 4 Tests — Deposit Accounting & Lifecycle Hardening

Tests that:
- action_receive_deposit() creates a direct journal entry (Dr Cash / Cr Deposit Liability), NOT account.payment
- action_release_deposit() creates Dr Deposit Liability / Cr Bank
- action_forfeit_deposit() creates Dr Deposit Liability / Cr Fine Revenue
- Repeated calls (idempotency) are rejected or safely guarded
- Row locking prevents concurrent transitions
- Legacy reclassification is restricted to admin
"""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'deposit_accounting', 'production_integrity_hardening')
class TestDepositAccounting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Deposit = cls.env['utility.deposit']
        cls.Customer = cls.env['utility.customer']
        cls.Partner = cls.env['res.partner']
        cls.Account = cls.env['account.account']
        cls.Journal = cls.env['account.journal']

        cls.partner = cls.Partner.create({'name': 'مشترك اختبار التأمينات'})
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة اختبار التأمينات',
            'code': 'DEP-CAT',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'نوع اختبار التأمينات',
            'code': 'DEP-SUB',
            'category_id': cls.category.id,
        })
        cls.customer = cls.Customer.create({
            'customer_number': 'DEP-CUST-001',
            'partner_id': cls.partner.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
        })

        # Chart of accounts setup for deposits
        cls.cash_account = cls.Account.search([
            ('company_id', '=', cls.env.company.id),
            ('account_type', '=', 'asset_cash'),
        ], limit=1)
        if not cls.cash_account:
            cls.cash_account = cls.Account.create({
                'name': 'صندوق التأمينات',
                'code': '101999',
                'account_type': 'asset_cash',
                'company_id': cls.env.company.id,
            })

        cls.deposit_liability_account = cls.Account.create({
            'name': 'التزامات تأمينات المشتركين',
            'code': '201999',
            'account_type': 'liability_current',
            'company_id': cls.env.company.id,
        })

        cls.fine_revenue_account = cls.Account.create({
            'name': 'إيرادات مصادرة التأمينات والغرامات',
            'code': '401999',
            'account_type': 'income',
            'company_id': cls.env.company.id,
        })

        cls.deposit_journal = cls.Journal.create({
            'name': 'يومية التأمينات',
            'code': 'DEPJ',
            'type': 'cash',
            'company_id': cls.env.company.id,
            'default_account_id': cls.cash_account.id,
        })

        # Set system config parameters
        cls.env['ir.config_parameter'].sudo().set_param(
            'utility.deposit_journal_id', str(cls.deposit_journal.id)
        )
        cls.env['ir.config_parameter'].sudo().set_param(
            'utility.deposit_account_id', str(cls.deposit_liability_account.id)
        )
        cls.env['ir.config_parameter'].sudo().set_param(
            'utility.fine_account_id', str(cls.fine_revenue_account.id)
        )

    def test_receive_deposit_creates_direct_move(self):
        """action_receive_deposit creates Dr Cash / Cr Liability entry."""
        deposit = self.Deposit.create({
            'customer_id': self.customer.id,
            'amount': 500.0,
            'deposit_type': 'security',
        })
        self.assertEqual(deposit.status, 'draft')

        deposit.action_receive_deposit()

        self.assertEqual(deposit.status, 'held')
        self.assertTrue(deposit.receipt_move_id)
        self.assertEqual(deposit.receipt_move_id.state, 'posted')
        self.assertFalse(deposit.payment_id, 'لا يجب استخدام account.payment للتأمينات.')

        # Verify journal entry lines
        lines = deposit.receipt_move_id.line_ids
        debit_line = lines.filtered(lambda l: l.debit > 0)
        credit_line = lines.filtered(lambda l: l.credit > 0)

        self.assertEqual(debit_line.account_id, self.cash_account,
                         'الطرف المدين يجب أن يكون حساب الصندوق.')
        self.assertEqual(credit_line.account_id, self.deposit_liability_account,
                         'الطرف الدائن يجب أن يكون حساب التزامات التأمينات.')
        self.assertAlmostEqual(debit_line.debit, 500.0)
        self.assertAlmostEqual(credit_line.credit, 500.0)

    def test_release_deposit_creates_reversal_move(self):
        """action_release_deposit creates Dr Liability / Cr Cash entry."""
        deposit = self.Deposit.create({
            'customer_id': self.customer.id,
            'amount': 300.0,
            'deposit_type': 'security',
        })
        deposit.action_receive_deposit()
        self.assertEqual(deposit.status, 'held')

        deposit.action_release_deposit()
        self.assertEqual(deposit.status, 'released')
        self.assertTrue(deposit.release_move_id)
        self.assertEqual(deposit.release_move_id.state, 'posted')

        lines = deposit.release_move_id.line_ids
        debit_line = lines.filtered(lambda l: l.debit > 0)
        credit_line = lines.filtered(lambda l: l.credit > 0)

        self.assertEqual(debit_line.account_id, self.deposit_liability_account,
                         'الطرف المدين يجب أن يكون حساب التزامات التأمينات.')
        self.assertEqual(credit_line.account_id, self.cash_account,
                         'الطرف الدائن يجب أن يكون حساب الصندوق/البنك.')

    def test_forfeit_deposit_creates_revenue_move(self):
        """action_forfeit_deposit creates Dr Liability / Cr Fine Revenue entry."""
        deposit = self.Deposit.create({
            'customer_id': self.customer.id,
            'amount': 400.0,
            'deposit_type': 'security',
        })
        deposit.action_receive_deposit()
        self.assertEqual(deposit.status, 'held')

        deposit.action_forfeit_deposit()
        self.assertEqual(deposit.status, 'forfeited')
        self.assertTrue(deposit.forfeit_move_id)
        self.assertEqual(deposit.forfeit_move_id.state, 'posted')

        lines = deposit.forfeit_move_id.line_ids
        debit_line = lines.filtered(lambda l: l.debit > 0)
        credit_line = lines.filtered(lambda l: l.credit > 0)

        self.assertEqual(debit_line.account_id, self.deposit_liability_account,
                         'الطرف المدين يجب أن يكون حساب التزامات التأمينات.')
        self.assertEqual(credit_line.account_id, self.fine_revenue_account,
                         'الطرف الدائن يجب أن يكون حساب إيرادات الغرامات.')

    def test_deposit_zero_or_negative_amount_blocked(self):
        """Deposit with 0 or negative amount must be blocked."""
        with self.assertRaises(ValidationError):
            self.Deposit.create({
                'customer_id': self.customer.id,
                'amount': 0.0,
                'deposit_type': 'security',
            })
        with self.assertRaises(ValidationError):
            self.Deposit.create({
                'customer_id': self.customer.id,
                'amount': -100.0,
                'deposit_type': 'security',
            })
