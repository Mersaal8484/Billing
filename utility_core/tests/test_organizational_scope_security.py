from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError


class TestOrganizationalScopeSecurity(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company

        # Create Region 1 and its child Branch (Area) 1-1
        self.region_a = self.env['utility.region'].create({
            'name': 'منطقة صنعاء',
            'code': 'REG_SANAA',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.branch_a1 = self.env['utility.region'].create({
            'name': 'فرع التحرير',
            'code': 'AREA_TAHREER',
            'type': 'area',
            'parent_id': self.region_a.id,
            'company_id': self.company.id,
        })

        # Create Region 2 and its child Branches (Area) 2-1 and 2-2
        self.region_b = self.env['utility.region'].create({
            'name': 'منطقة عدن',
            'code': 'REG_ADEN',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.branch_b1 = self.env['utility.region'].create({
            'name': 'فرع كريتر',
            'code': 'AREA_CRATER',
            'type': 'area',
            'parent_id': self.region_b.id,
            'company_id': self.company.id,
        })
        self.branch_b2 = self.env['utility.region'].create({
            'name': 'فرع المعلا',
            'code': 'AREA_MOALLA',
            'type': 'area',
            'parent_id': self.region_b.id,
            'company_id': self.company.id,
        })

        # Partners
        self.partner_a = self.env['res.partner'].create({
            'name': 'مشترك صنعاء',
            'region_id': self.region_a.id,
            'area_id': self.branch_a1.id,
            'company_id': self.company.id,
        })
        self.partner_b = self.env['res.partner'].create({
            'name': 'مشترك عدن',
            'region_id': self.region_b.id,
            'area_id': self.branch_b1.id,
            'company_id': self.company.id,
        })

        # Customers
        self.customer_a = self.env['utility.customer'].create({
            'name': 'حساب صنعاء 01',
            'partner_id': self.partner_a.id,
            'customer_number': 'CUST_SANAA_01',
            'company_id': self.company.id,
        })
        self.customer_b = self.env['utility.customer'].create({
            'name': 'حساب عدن 01',
            'partner_id': self.partner_b.id,
            'customer_number': 'CUST_ADEN_01',
            'company_id': self.company.id,
        })

        # Operational Users
        self.user_restricted = self.env['res.users'].create({
            'name': 'مستخدم صنعاء',
            'login': 'user_sanaa_test',
            'email': 'sanaa_test@utility.local',
            'scope_mode': 'restricted',
            'assigned_region_ids': [(6, 0, [self.region_a.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_supervisor').id])],
        })
        self.user_empty_scope = self.env['res.users'].create({
            'name': 'مستخدم بدون نطاق',
            'login': 'user_empty_scope_test',
            'email': 'empty_test@utility.local',
            'scope_mode': 'restricted',
            'assigned_region_ids': [(6, 0, [])],
            'assigned_branch_ids': [(6, 0, [])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_supervisor').id])],
        })

    def test_01_effective_branch_calculation(self):
        """Assigned Region A auto-includes branch A1. Explicit branch B2 does NOT add parent Region B to effective regions."""
        self.user_restricted.write({
            'assigned_branch_ids': [(6, 0, [self.branch_b2.id])],
        })
        eff_branches = self.user_restricted._get_effective_branch_ids()
        eff_regions = self.user_restricted._get_effective_region_ids()

        self.assertIn(self.branch_a1.id, eff_branches)
        self.assertIn(self.branch_b2.id, eff_branches)
        self.assertNotIn(self.branch_b1.id, eff_branches)

        self.assertIn(self.region_a.id, eff_regions)
        self.assertNotIn(self.region_b.id, eff_regions)

    def test_02_fail_closed_empty_scope(self):
        """Restricted user with empty regions/branches must see ZERO operational customers."""
        customers = self.env['utility.customer'].with_user(self.user_empty_scope).search([])
        self.assertEqual(len(customers), 0)

    def test_03_customer_isolation(self):
        """Restricted user in Region A sees only Customer A, not Customer B."""
        customers = self.env['utility.customer'].with_user(self.user_restricted).search([])
        self.assertIn(self.customer_a, customers)
        self.assertNotIn(self.customer_b, customers)

    def test_04_global_admin_bypass(self):
        """Admin user has global scope and sees all customers."""
        admin_user = self.env.ref('base.user_admin')
        customers = self.env['utility.customer'].with_user(admin_user).search([])
        self.assertIn(self.customer_a, customers)
        self.assertIn(self.customer_b, customers)
