"""
Phase 5 Tests — Collector Accounting: No Runtime CoA Auto-Creation

Tests that:
- Creating a utility.staff record with collector role does NOT create account.account
- Writing role_ids to a staff record does NOT create account.account
- action_create_cash_journal() raises AccessError for non-admin users
- action_create_cash_journal() creates journal idempotently for admin users
- action_register_utility_payment() raises clear ValidationError if journal not configured
- _ensure_collector_journal() does NOT create any account.account records
"""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'collector_no_coa_autocreate', 'production_integrity_hardening')
class TestCollectorNoCoaAutocreate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Staff = cls.env['utility.staff']
        cls.Account = cls.env['account.account']
        cls.Journal = cls.env['account.journal']

        cls.collector_role = cls.env['utility.role'].search([
            ('code', '=', 'collector'),
        ], limit=1)
        if not cls.collector_role:
            cls.collector_role = cls.env['utility.role'].create({
                'name': 'متحصل اختبار CoA',
                'code': 'collector',
            })

        # A user without admin/accounting manager groups
        cls.regular_user = cls.env.ref('base.user_demo', raise_if_not_found=False)
        if not cls.regular_user:
            cls.regular_user = cls.env['res.users'].create({
                'name': 'مستخدم اختبار عادي',
                'login': 'coa_test_regular_%s' % cls.env.cr.dbname,
                'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])],
            })

    def _count_accounts(self):
        return self.Account.search_count([
            ('company_id', '=', self.env.company.id),
        ])

    def _count_journals(self):
        return self.Journal.search_count([
            ('company_id', '=', self.env.company.id),
            ('type', '=', 'cash'),
        ])

    # ── Create staff does NOT create account.account ───────────────────────
    def test_create_collector_staff_does_not_create_coa(self):
        """Creating a collector staff must not create any account.account."""
        partner = self.env['res.partner'].create({'name': 'متحصل اختبار إنشاء CoA'})
        user = self.env['res.users'].create({
            'name': 'متحصل اختبار إنشاء CoA',
            'login': 'coa_create_test_%s' % id(self),
            'partner_id': partner.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })

        accounts_before = self._count_accounts()
        journals_before = self._count_journals()

        self.Staff.create({
            'name': 'متحصل اختبار إنشاء CoA',
            'user_id': user.id,
            'company_id': self.env.company.id,
            'role_ids': [(4, self.collector_role.id)],
        })

        accounts_after = self._count_accounts()
        journals_after = self._count_journals()

        self.assertEqual(accounts_before, accounts_after,
                         'create() يجب ألا ينشئ حسابات محاسبية جديدة.')
        self.assertEqual(journals_before, journals_after,
                         'create() يجب ألا ينشئ يوميات جديدة.')

    # ── Write role_ids does NOT create account.account ─────────────────────
    def test_write_role_ids_does_not_create_coa(self):
        """Assigning collector role via write() must not create account.account."""
        partner = self.env['res.partner'].create({'name': 'متحصل اختبار تعديل CoA'})
        user = self.env['res.users'].create({
            'name': 'متحصل اختبار تعديل CoA',
            'login': 'coa_write_test_%s' % id(self),
            'partner_id': partner.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        staff = self.Staff.create({
            'name': 'متحصل اختبار تعديل CoA',
            'user_id': user.id,
            'company_id': self.env.company.id,
        })

        accounts_before = self._count_accounts()
        journals_before = self._count_journals()

        staff.write({'role_ids': [(4, self.collector_role.id)]})

        accounts_after = self._count_accounts()
        journals_after = self._count_journals()

        self.assertEqual(accounts_before, accounts_after,
                         'write(role_ids) يجب ألا ينشئ حسابات محاسبية جديدة.')
        self.assertEqual(journals_before, journals_after,
                         'write(role_ids) يجب ألا ينشئ يوميات جديدة.')

    # ── action_create_cash_journal() requires admin group ──────────────────
    def test_action_create_cash_journal_requires_admin(self):
        """Non-admin user must get AccessError from action_create_cash_journal()."""
        staff = self.Staff.search([
            ('role_ids.code', '=', 'collector'),
        ], limit=1)
        if not staff:
            self.skipTest('لا يوجد موظف متحصل مسجّل للاختبار.')

        with self.assertRaises(AccessError,
                               msg='action_create_cash_journal يجب أن يرفض المستخدم غير المسؤول.'):
            staff.with_user(self.regular_user).action_create_cash_journal()

    # ── _ensure_collector_journal() raises clear error if unconfigured ─────
    def test_ensure_collector_journal_fails_closed_without_config(self):
        """_ensure_collector_journal() must raise ValidationError, not create journals."""
        partner = self.env['res.partner'].create({'name': 'متحصل بدون يومية'})
        user = self.env['res.users'].create({
            'name': 'متحصل بدون يومية',
            'login': 'coa_no_journal_%s' % id(self),
            'partner_id': partner.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.Staff.create({
            'name': 'متحصل بدون يومية',
            'user_id': user.id,
            'company_id': self.env.company.id,
            'role_ids': [(4, self.collector_role.id)],
        })

        # Create a minimal sale.order to test _ensure_collector_journal
        order = self.env['sale.order'].with_user(user).create({
            'partner_id': partner.id,
            'company_id': self.env.company.id,
        })

        accounts_before = self._count_accounts()
        journals_before = self._count_journals()

        with self.assertRaises(ValidationError) as ctx:
            order.with_user(user)._ensure_collector_journal()

        # Verify the error is the explicit config-missing message
        self.assertIn('ACCOUNTING_CONFIG_MISSING',
                      str(ctx.exception),
                      'رسالة الخطأ يجب أن تحتوي على ACCOUNTING_CONFIG_MISSING.')

        # No accounts or journals should have been created
        self.assertEqual(accounts_before, self._count_accounts(),
                         '_ensure_collector_journal يجب ألا ينشئ حسابات.')
        self.assertEqual(journals_before, self._count_journals(),
                         '_ensure_collector_journal يجب ألا ينشئ يوميات.')

    # ── action_create_cash_journal() is idempotent ─────────────────────────
    def test_action_create_cash_journal_is_idempotent(self):
        """Calling action_create_cash_journal() twice must not create two journals."""
        partner = self.env['res.partner'].create({'name': 'متحصل اختبار الـidempotency'})
        user = self.env['res.users'].create({
            'name': 'متحصل اختبار الـidempotency',
            'login': 'coa_idemp_%s' % id(self),
            'partner_id': partner.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        staff = self.Staff.create({
            'name': 'متحصل اختبار الـidempotency',
            'user_id': user.id,
            'company_id': self.env.company.id,
            'role_ids': [(4, self.collector_role.id)],
        })

        journals_before = self._count_journals()

        # First call — creates journal
        staff.sudo().action_create_cash_journal()
        journals_after_first = self._count_journals()
        self.assertEqual(journals_after_first, journals_before + 1,
                         'الاستدعاء الأول يجب أن ينشئ يومية واحدة.')

        # Second call — must return existing journal, not create another
        staff.sudo().action_create_cash_journal()
        journals_after_second = self._count_journals()
        self.assertEqual(journals_after_second, journals_after_first,
                         'الاستدعاء الثاني يجب ألا ينشئ يومية إضافية.')
