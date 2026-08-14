"""
Wave 17 (+1) — Canonical Mutation Integrity Tests

Verifies that restricted organizational users cannot create or write
utility.customer / utility.meter records whose resolved canonical
geography falls outside their assigned scope.

Key design decisions:
- utility.customer.region_id/area_id are related-stored from partner_id.
  Scope check is post-create on resolved partner_id.region_id/area_id.
- utility.meter.region_id/area_id are computed-stored from _compute_location_fields.
  Scope check validates canonical ownership fields per connection_type.
- utility_scope_bypass context is gated to env.su OR group_utility_admin ONLY.
  A restricted user passing it via RPC will NOT get the bypass (P0 fix).
- Fail-closed: restricted user creating utility.customer with NO geography = rejected.
- Fail-closed: meter with non-'not_connected' type and unresolved owner geography = rejected.
"""
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestWave17MutationIntegrity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Region = cls.env['utility.region']
        cls.region_a = Region.create({'name': 'W17MI Region A', 'type': 'region', 'code': 'W17MI-RA'})
        cls.region_b = Region.create({'name': 'W17MI Region B', 'type': 'region', 'code': 'W17MI-RB'})
        cls.branch_a = Region.create({
            'name': 'W17MI Branch A1', 'type': 'area', 'code': 'W17MI-BA',
            'parent_id': cls.region_a.id,
        })
        cls.branch_b = Region.create({
            'name': 'W17MI Branch B1', 'type': 'area', 'code': 'W17MI-BB',
            'parent_id': cls.region_b.id,
        })

        Partner = cls.env['res.partner']
        cls.partner_a = Partner.create({'name': 'W17MI Partner A', 'region_id': cls.region_a.id, 'area_id': cls.branch_a.id})
        cls.partner_b = Partner.create({'name': 'W17MI Partner B', 'region_id': cls.region_b.id, 'area_id': cls.branch_b.id})

        cats = cls.env['utility.subscriber.category'].search([], limit=1)
        cls.category = cats if cats else cls.env['utility.subscriber.category'].create({'name': 'W17MI Cat'})
        subs = cls.env['utility.subscriber'].search([], limit=1)
        cls.subscriber = subs if subs else cls.env['utility.subscriber'].create({'name': 'W17MI Sub', 'category_id': cls.category.id})

        # Admin (superuser-context) creates baseline customers to avoid scope blocking
        cls.customer_a = cls.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': cls.partner_a.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
        })
        partner_b_cust = Partner.create({'name': 'W17MI Partner B Cust', 'region_id': cls.region_b.id, 'area_id': cls.branch_b.id})
        cls.customer_b = cls.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': partner_b_cust.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
        })

        cls.route_a = cls.env['utility.route'].create({'name': 'W17MI Route A', 'code': 'W17MI-RTA', 'region_id': cls.region_a.id, 'area_id': cls.branch_a.id})
        cls.route_b = cls.env['utility.route'].create({'name': 'W17MI Route B', 'code': 'W17MI-RTB', 'region_id': cls.region_b.id, 'area_id': cls.branch_b.id})

        # Restricted user: Region A only
        cls.user_a = cls.env['res.users'].create({
            'name': 'W17MI User Region A',
            'login': 'w17mi_user_a@test.local',
            'groups_id': [(4, cls.env.ref('utility_core.group_utility_supervisor').id)],
            'scope_mode': 'restricted',
            'assigned_region_ids': [(4, cls.region_a.id)],
        })

    # -----------------------------------------------------------------------
    # 1. utility.customer CREATE cross-scope — rejected
    # -----------------------------------------------------------------------

    def test_01_customer_create_foreign_region_rejected(self):
        """Restricted Region A user cannot create a customer in Region B."""
        partner_b_new = self.env['res.partner'].create({
            'name': 'W17MI New B', 'region_id': self.region_b.id, 'area_id': self.branch_b.id,
        })
        with self.assertRaises(AccessError):
            self.env['utility.customer'].with_user(self.user_a).create({
                'partner_id': partner_b_new.id,
                'category_id': self.category.id,
                'subscriber_id': self.subscriber.id,
            })

    def test_02_customer_create_own_region_allowed(self):
        """Restricted Region A user CAN create a customer in Region A."""
        partner_a_new = self.env['res.partner'].create({
            'name': 'W17MI New A', 'region_id': self.region_a.id, 'area_id': self.branch_a.id,
        })
        cust = self.env['utility.customer'].with_user(self.user_a).create({
            'partner_id': partner_a_new.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })
        self.assertTrue(cust.id)

    # -----------------------------------------------------------------------
    # 2. utility.customer CREATE with NO geography — FAIL-CLOSED (P1 fix)
    # -----------------------------------------------------------------------

    def test_03_customer_create_no_geography_fail_closed(self):
        """FAIL-CLOSED: restricted user creating utility.customer whose partner has
        no region/area is REJECTED. utility.customer is the organizational anchor —
        unscoped customers are forbidden for restricted users."""
        partner_no_geo = self.env['res.partner'].create({'name': 'W17MI No Geo'})
        with self.assertRaises(AccessError, msg="Expected AccessError for customer with no geography"):
            self.env['utility.customer'].with_user(self.user_a).create({
                'partner_id': partner_no_geo.id,
                'category_id': self.category.id,
                'subscriber_id': self.subscriber.id,
            })

    # -----------------------------------------------------------------------
    # 3. utility.customer WRITE cross-scope
    # -----------------------------------------------------------------------

    def test_04_customer_write_foreign_route_rejected(self):
        """Restricted Region A user cannot assign Route B to a customer."""
        with self.assertRaises(AccessError):
            self.customer_a.with_user(self.user_a).write({'route_id': self.route_b.id})

    def test_05_customer_write_own_route_allowed(self):
        """Restricted Region A user CAN assign Route A to their customer."""
        self.customer_a.with_user(self.user_a).write({'route_id': self.route_a.id})
        self.assertEqual(self.customer_a.route_id, self.route_a)

    # -----------------------------------------------------------------------
    # 4. utility.meter CREATE with foreign canonical owner
    # -----------------------------------------------------------------------

    def test_06_meter_create_subscriber_foreign_customer_rejected(self):
        """Restricted Region A user cannot create a meter linked to customer_b (Region B)."""
        with self.assertRaises(AccessError):
            self.env['utility.meter'].with_user(self.user_a).create({
                'meter_number': 'W17MI-MTR-FAIL',
                'connection_type': 'subscriber',
                'customer_id': self.customer_b.id,
                'payment_type': 'postpaid',
            })

    def test_07_meter_create_subscriber_own_customer_allowed(self):
        """Restricted Region A user CAN create a meter linked to customer_a (Region A)."""
        meter = self.env['utility.meter'].with_user(self.user_a).create({
            'meter_number': 'W17MI-MTR-OK',
            'connection_type': 'subscriber',
            'customer_id': self.customer_a.id,
            'payment_type': 'postpaid',
        })
        self.assertTrue(meter.id)

    def test_08_meter_create_not_connected_allowed(self):
        """Restricted user can create a not_connected meter (no canonical owner)."""
        meter = self.env['utility.meter'].with_user(self.user_a).create({
            'meter_number': 'W17MI-MTR-NC',
            'connection_type': 'not_connected',
            'payment_type': 'manual',
        })
        self.assertTrue(meter.id)

    # -----------------------------------------------------------------------
    # 5. utility.meter WRITE — reassign to foreign canonical owner
    # -----------------------------------------------------------------------

    def test_09_meter_write_reassign_foreign_customer_rejected(self):
        """Restricted Region A user cannot reassign allowed meter to customer_b (Region B)."""
        meter = self.env['utility.meter'].with_context(utility_scope_bypass=True).create({
            'meter_number': 'W17MI-MTR-REASN',
            'connection_type': 'subscriber',
            'customer_id': self.customer_a.id,
            'payment_type': 'postpaid',
        })
        with self.assertRaises(AccessError):
            meter.with_user(self.user_a).write({'customer_id': self.customer_b.id})

    # -----------------------------------------------------------------------
    # 6. P0 Fix: utility_scope_bypass is NOT a privilege escalation vector
    # -----------------------------------------------------------------------

    def test_10_non_admin_scope_bypass_context_rejected(self):
        """P0: A non-admin restricted user passing utility_scope_bypass=True via
        context (simulating crafted RPC) must NOT get the bypass.
        This confirms the vulnerability is closed."""
        partner_b_new = self.env['res.partner'].create({
            'name': 'W17MI P0 Test B', 'region_id': self.region_b.id, 'area_id': self.branch_b.id,
        })
        with self.assertRaises(AccessError,
                               msg="Non-admin restricted user must NOT benefit from utility_scope_bypass"):
            self.env['utility.customer'].with_user(self.user_a).with_context(
                utility_scope_bypass=True  # Simulates crafted RPC context injection
            ).create({
                'partner_id': partner_b_new.id,
                'category_id': self.category.id,
                'subscriber_id': self.subscriber.id,
            })

    def test_11_admin_scope_bypass_context_allowed(self):
        """Admin-context bypass (env.su or group_utility_admin) remains available
        for legitimate migration/admin operations."""
        partner_b_admin = self.env['res.partner'].create({
            'name': 'W17MI Admin Bypass B', 'region_id': self.region_b.id, 'area_id': self.branch_b.id,
        })
        # env is admin (running as ORM admin in test) — bypass allowed
        cust = self.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': partner_b_admin.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })
        self.assertTrue(cust.id)
