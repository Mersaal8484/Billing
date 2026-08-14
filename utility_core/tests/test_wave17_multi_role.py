"""
Wave 17 — Multi-Role Record Rule Composition Tests

Verifies that implied group hierarchies do NOT grant broader regional access:
- Billing Manager (implies Supervisor → Collector + Cashier + Technician + Readonly)
  restricted to Region A must NOT see Region B records.
- Revenue Manager (implies Billing Manager) same restriction.
- Auditor restricted to Region A must NOT see Region B.
- Scope reassignment: changing user scope takes effect on next ORM call.
- Collector (Region A, Route A-01): Route × Region intersection preserved.
"""
from odoo.tests.common import TransactionCase


class TestWave17MultiRole(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Region = cls.env['utility.region']
        cls.region_a = Region.create({'name': 'W17MR Region A', 'type': 'region', 'code': 'W17MR-RA'})
        cls.region_b = Region.create({'name': 'W17MR Region B', 'type': 'region', 'code': 'W17MR-RB'})
        cls.branch_a = Region.create({'name': 'W17MR Branch A', 'type': 'area', 'code': 'W17MR-BA', 'parent_id': cls.region_a.id})
        cls.branch_b = Region.create({'name': 'W17MR Branch B', 'type': 'area', 'code': 'W17MR-BB', 'parent_id': cls.region_b.id})

        Partner = cls.env['res.partner']
        cls.partner_a = Partner.create({'name': 'W17MR PartnerA', 'region_id': cls.region_a.id, 'area_id': cls.branch_a.id})
        cls.partner_b = Partner.create({'name': 'W17MR PartnerB', 'region_id': cls.region_b.id, 'area_id': cls.branch_b.id})

        cats = cls.env['utility.subscriber.category'].search([], limit=1)
        cls.category = cats if cats else cls.env['utility.subscriber.category'].create({'name': 'W17MR Cat'})
        subs = cls.env['utility.subscriber'].search([], limit=1)
        cls.subscriber = subs if subs else cls.env['utility.subscriber'].create({'name': 'W17MR Sub', 'category_id': cls.category.id})

        cls.customer_a = cls.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': cls.partner_a.id, 'category_id': cls.category.id, 'subscriber_id': cls.subscriber.id,
        })
        cls.customer_b = cls.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': cls.partner_b.id, 'category_id': cls.category.id, 'subscriber_id': cls.subscriber.id,
        })

        # Route in Region A and B
        cls.route_a01 = cls.env['utility.route'].create({'name': 'W17MR Route A-01', 'code': 'W17MR-A01', 'region_id': cls.region_a.id, 'area_id': cls.branch_a.id})
        cls.route_a02 = cls.env['utility.route'].create({'name': 'W17MR Route A-02', 'code': 'W17MR-A02', 'region_id': cls.region_a.id, 'area_id': cls.branch_a.id})
        cls.route_b01 = cls.env['utility.route'].create({'name': 'W17MR Route B-01', 'code': 'W17MR-B01', 'region_id': cls.region_b.id, 'area_id': cls.branch_b.id})

        # Customers on each route
        partner_a01 = Partner.create({'name': 'W17MR CustA01', 'region_id': cls.region_a.id, 'area_id': cls.branch_a.id})
        partner_a02 = Partner.create({'name': 'W17MR CustA02', 'region_id': cls.region_a.id, 'area_id': cls.branch_a.id})
        cls.cust_route_a01 = cls.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': partner_a01.id, 'category_id': cls.category.id, 'subscriber_id': cls.subscriber.id,
            'route_id': cls.route_a01.id,
        })
        cls.cust_route_a02 = cls.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': partner_a02.id, 'category_id': cls.category.id, 'subscriber_id': cls.subscriber.id,
            'route_id': cls.route_a02.id,
        })

        # Create users
        group_billing_mgr = cls.env.ref('utility_core.group_utility_billing_manager').id
        group_revenue_mgr = cls.env.ref('utility_core.group_utility_revenue_manager').id
        group_auditor = cls.env.ref('utility_core.group_utility_auditor').id
        group_collector = cls.env.ref('utility_core.group_utility_collector').id

        cls.billing_mgr_a = cls.env['res.users'].create({
            'name': 'W17MR Billing Mgr A', 'login': 'w17mr_billmgr_a@test.local',
            'groups_id': [(4, group_billing_mgr)],
            'scope_mode': 'restricted', 'assigned_region_ids': [(4, cls.region_a.id)],
        })
        cls.revenue_mgr_a = cls.env['res.users'].create({
            'name': 'W17MR Revenue Mgr A', 'login': 'w17mr_revmgr_a@test.local',
            'groups_id': [(4, group_revenue_mgr)],
            'scope_mode': 'restricted', 'assigned_region_ids': [(4, cls.region_a.id)],
        })
        cls.auditor_a = cls.env['res.users'].create({
            'name': 'W17MR Auditor A', 'login': 'w17mr_auditor_a@test.local',
            'groups_id': [(4, group_auditor)],
            'scope_mode': 'restricted', 'assigned_region_ids': [(4, cls.region_a.id)],
        })
        cls.collector_a_route_a01 = cls.env['res.users'].create({
            'name': 'W17MR Collector A Route A01', 'login': 'w17mr_coll_a@test.local',
            'groups_id': [(4, group_collector)],
            'scope_mode': 'restricted',
            'assigned_region_ids': [(4, cls.region_a.id)],
            'assigned_route_ids': [(4, cls.route_a01.id)],
        })
        # User for reassignment test
        cls.user_reassign = cls.env['res.users'].create({
            'name': 'W17MR Reassign User', 'login': 'w17mr_reassign@test.local',
            'groups_id': [(4, cls.env.ref('utility_core.group_utility_supervisor').id)],
            'scope_mode': 'restricted', 'assigned_region_ids': [(4, cls.region_a.id)],
        })

    # -----------------------------------------------------------------------
    # 1. Billing Manager (implied: Supervisor→Collector+Cashier+Technician+Readonly)
    # -----------------------------------------------------------------------

    def test_01_billing_manager_region_a_cannot_see_region_b(self):
        """Billing Manager restricted to Region A must NOT see Region B customers
        despite inheriting Collector/Cashier/Readonly groups which have route rules."""
        customers = self.env['utility.customer'].with_user(self.billing_mgr_a).search([])
        customer_ids = customers.ids
        self.assertIn(self.customer_a.id, customer_ids,
                      "Billing Manager should see Region A customer")
        self.assertNotIn(self.customer_b.id, customer_ids,
                         "Billing Manager must NOT see Region B customer via implied groups")

    # -----------------------------------------------------------------------
    # 2. Revenue Manager (implied: Billing Manager → all below)
    # -----------------------------------------------------------------------

    def test_02_revenue_manager_region_a_cannot_see_region_b(self):
        """Revenue Manager restricted to Region A must NOT see Region B."""
        customers = self.env['utility.customer'].with_user(self.revenue_mgr_a).search([])
        self.assertIn(self.customer_a.id, customers.ids)
        self.assertNotIn(self.customer_b.id, customers.ids,
                         "Revenue Manager must NOT see Region B customer")

    # -----------------------------------------------------------------------
    # 3. Auditor — readonly, Region A
    # -----------------------------------------------------------------------

    def test_03_auditor_region_a_cannot_see_region_b(self):
        """Auditor restricted to Region A must NOT see Region B customers."""
        customers = self.env['utility.customer'].with_user(self.auditor_a).search([])
        self.assertNotIn(self.customer_b.id, customers.ids,
                         "Auditor must NOT see Region B customer")

    # -----------------------------------------------------------------------
    # 4. Scope reassignment: change Region A → Region B takes effect immediately
    # -----------------------------------------------------------------------

    def test_04_scope_reassignment_takes_effect_on_next_query(self):
        """Changing user scope from Region A to Region B must take effect on the next ORM query."""
        # Verify initially: user sees Region A, not Region B
        customers_before = self.env['utility.customer'].with_user(self.user_reassign).search([])
        self.assertIn(self.customer_a.id, customers_before.ids, "Should see A before reassign")
        self.assertNotIn(self.customer_b.id, customers_before.ids, "Should NOT see B before reassign")

        # Admin changes scope to Region B
        self.user_reassign.write({
            'assigned_region_ids': [(5,), (4, self.region_b.id)],
        })

        # After reassignment: user should see Region B, not Region A
        customers_after = self.env['utility.customer'].with_user(self.user_reassign).search([])
        self.assertNotIn(self.customer_a.id, customers_after.ids, "Should NOT see A after reassign to B")
        self.assertIn(self.customer_b.id, customers_after.ids, "Should see B after reassign")

        # Restore for cleanup
        self.user_reassign.write({'assigned_region_ids': [(5,), (4, self.region_a.id)]})

    # -----------------------------------------------------------------------
    # 5. Collector — Route × Region intersection
    # -----------------------------------------------------------------------

    def test_05_collector_route_region_intersection(self):
        """Collector in Region A with Route A-01 should see:
        - Customer on Route A-01 → VISIBLE
        - Customer on Route A-02 (same Region, different Route) → HIDDEN
        - Customer in Region B → HIDDEN
        """
        customers = self.env['utility.customer'].with_user(self.collector_a_route_a01).search([])
        ids = customers.ids

        self.assertIn(self.cust_route_a01.id, ids,
                      "Collector with Route A-01 should see customer on that route")
        self.assertNotIn(self.cust_route_a02.id, ids,
                         "Collector with Route A-01 must NOT see customer on Route A-02")
        self.assertNotIn(self.customer_b.id, ids,
                         "Collector must NOT see Region B customer")

    # -----------------------------------------------------------------------
    # 6. Scope write protection: non-admin cannot change assigned_region_ids
    # -----------------------------------------------------------------------

    def test_06_non_admin_cannot_write_scope_fields(self):
        """A regular Supervisor cannot change their own scope assignments."""
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            self.billing_mgr_a.with_user(self.billing_mgr_a).write({
                'assigned_region_ids': [(4, self.region_b.id)],
            })
