"""
Phase 6 Tests — Financial Settlement Workflow & Segregation of Duties

Tests that:
- Workflow: draft → submitted → approved → applied
- Self-approval blocked (AccessError for approver == submitter)
- Applying requires approved state
- Immutability of applied records (write raises ValidationError)
- Unlink blocked for non-draft records
- Cancel from applied is blocked
"""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'financial_settlement_workflow', 'production_integrity_hardening')
class TestFinancialSettlementWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Settlement = cls.env['utility.financial.settlement']
        cls.Customer = cls.env['utility.customer']
        cls.Partner = cls.env['res.partner']
        cls.Account = cls.env['account.account']
        cls.Journal = cls.env['account.journal']

        cls.partner = cls.Partner.create({'name': 'مشترك اختبار التسوية المالية'})
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة اختبار التسوية المالية',
            'code': 'FIN-SET-CAT',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'نوع اختبار التسوية المالية',
            'code': 'FIN-SET-SUB',
            'category_id': cls.category.id,
        })
        cls.customer = cls.Customer.create({
            'customer_number': 'FIN-SET-CUST-001',
            'partner_id': cls.partner.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
        })

        cls.income_account = cls.Account.search([
            ('company_id', '=', cls.env.company.id),
            ('account_type', '=', 'income'),
        ], limit=1)
        if not cls.income_account:
            cls.income_account = cls.Account.create({
                'name': 'حساب التسويات المالية',
                'code': '401888',
                'account_type': 'income',
                'company_id': cls.env.company.id,
            })

        cls.sale_journal = cls.Journal.search([
            ('company_id', '=', cls.env.company.id),
            ('type', '=', 'sale'),
        ], limit=1)
        if not cls.sale_journal:
            cls.sale_journal = cls.Journal.create({
                'name': 'يومية التسويات',
                'code': 'FINSJ',
                'type': 'sale',
                'company_id': cls.env.company.id,
            })

        cls.env['ir.config_parameter'].sudo().set_param(
            'utility.settlement_journal_id', str(cls.sale_journal.id)
        )
        cls.env['ir.config_parameter'].sudo().set_param(
            'utility.settlement_account_id', str(cls.income_account.id)
        )

        mgr_group = cls.env.ref('utility_core.group_utility_billing_manager', raise_if_not_found=False)
        groups = [cls.env.ref('base.group_user').id]
        if mgr_group:
            groups.append(mgr_group.id)

        cls.user1 = cls.env['res.users'].create({
            'name': 'مستخدم تسوية 1',
            'login': 'fin_settle_u1_%s' % id(cls),
            'groups_id': [(6, 0, groups)],
        })
        cls.user2 = cls.env['res.users'].create({
            'name': 'مستخدم تسوية 2',
            'login': 'fin_settle_u2_%s' % id(cls),
            'groups_id': [(6, 0, groups)],
        })

    def test_full_workflow_happy_path(self):
        """Happy path: draft -> submitted -> approved -> applied."""
        settlement = self.Settlement.with_user(self.user1).create({
            'account_id': self.customer.id,
            'settlement_type': 'credit',
            'amount': 250.0,
            'reason': 'اختبار مسار التسوية المالية',
            'source_document': 'قرار إداري رقم 101',
            'source_reference': 'DEC-2026-101',
        })
        self.assertEqual(settlement.state, 'draft')

        # Submit
        settlement.action_submit()
        self.assertEqual(settlement.state, 'submitted')
        self.assertEqual(settlement.submitted_by_id, self.user1)

        # Approve by user2 (different user)
        settlement.with_user(self.user2).action_approve()
        self.assertEqual(settlement.state, 'approved')
        self.assertEqual(settlement.approved_by_id, self.user2)

        # Apply
        settlement.with_user(self.user2).action_apply_settlement()
        self.assertEqual(settlement.state, 'applied')
        self.assertTrue(settlement.move_id)
        self.assertEqual(settlement.move_id.state, 'posted')
        self.assertEqual(settlement.move_id.move_type, 'out_refund')

    def test_submit_without_source_blocked(self):
        """Submitting a financial settlement without source document/reference must raise ValidationError."""
        settlement = self.Settlement.with_user(self.user1).create({
            'account_id': self.customer.id,
            'settlement_type': 'credit',
            'amount': 180.0,
            'reason': 'اختبار إلزامية المستند المصدري',
        })
        with self.assertRaises(ValidationError):
            settlement.action_submit()

    def test_self_approval_blocked(self):
        """User1 cannot approve a settlement submitted by User1."""
        settlement = self.Settlement.with_user(self.user1).create({
            'account_id': self.customer.id,
            'settlement_type': 'credit',
            'amount': 150.0,
            'reason': 'اختبار منع الاعتماد الذاتي',
            'source_document': 'تقرير تدقيق داخلي',
            'source_reference': 'AUD-2026-004',
        })
        settlement.action_submit()

        with self.assertRaises(AccessError,
                               msg='يجب منع الموظف من اعتماد تسويته بنفسه.'):
            settlement.with_user(self.user1).action_approve()

    def test_applied_settlement_immutable(self):
        """Modifying financial fields on applied settlement must raise ValidationError."""
        settlement = self.Settlement.with_user(self.user1).create({
            'account_id': self.customer.id,
            'settlement_type': 'credit',
            'amount': 100.0,
            'reason': 'اختبار الحماية ضد التعديل',
            'source_document': 'توجيه مدير عام',
            'source_reference': 'DIR-2026-012',
        })
        settlement.action_submit()
        settlement.with_user(self.user2).action_approve()
        settlement.with_user(self.user2).action_apply_settlement()

        with self.assertRaises(ValidationError):
            settlement.write({'amount': 200.0})

        with self.assertRaises(ValidationError):
            settlement.unlink()

    def test_cancel_applied_blocked(self):
        """Cancelling applied settlement must raise ValidationError."""
        settlement = self.Settlement.with_user(self.user1).create({
            'account_id': self.customer.id,
            'settlement_type': 'debit',
            'amount': 50.0,
            'reason': 'اختبار منع إلغاء المطبق',
            'source_document': 'محضر معاينة فنية',
            'source_reference': 'INSP-2026-88',
        })
        settlement.action_submit()
        settlement.with_user(self.user2).action_approve()
        settlement.with_user(self.user2).action_apply_settlement()

        with self.assertRaises(ValidationError):
            settlement.action_cancel()
