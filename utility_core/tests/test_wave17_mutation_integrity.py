"""
Wave 17 — Canonical Mutation Integrity Tests

Verifies that restricted organizational users cannot create or write
utility.customer / utility.meter records whose resolved canonical
geography falls outside their assigned scope.

Key design decisions (per P1 corrections):
- utility.customer.region_id/area_id are related-stored from partner_id,
  so we check post-create resolved geography, not raw vals keys.
- utility.meter.region_id/area_id are computed-stored from _compute_location_fields;
  we check canonical ownership fields (customer_id, linked_transformer_id, etc.).
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

        cls.user_a = cls.env['res.users'].create({
            'name': 'W17MI User Region A',
            'login': 'w17mi_user_a@test.local',
            'groups_id': [(4, cls.env.ref('utility_core.group_utility_supervisor').id)],
            'scope_mode': 'restricted',
            'assigned_region_ids': [(4, cls.region_a.id)],
        })

    def test_01_customer_create_foreign_region_rejected(self):
        partner_b_new = self.env['res.partner'].create({'name': 'W17MI New B', 'region_id': self.region_b.id, 'area_id': self.branch_b.id})
        with self.assertRaises(AccessError):
            self.env['utility.customer'].with_user(self.user_a).create({
                'partner_id': partner_b_new.id,
                'category_id': self.category.id,
                'subscriber_id': self.subscriber.id,
            })

    def test_02_customer_create_own_region_allowed(self):
        partner_a_new = self.env['res.partner'].create({'name': 'W17MI New A', 'region_id': self.region_a.id, 'area_id': self.branch_a.id})
        cust = self.env['utility.customer'].with_user(self.user_a).create({
            'partner_id': partner_a_new.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })
        self.assertTrue(cust.id)

    def test_03_customer_create_no_geography_allowed(self):
        partner_no_geo = self.env['res.partner'].create({'name': 'W17MI No Geo'})
        cust = self.env['utility.customer'].with_user(self.user_a).create({
            'partner_id': partner_no_geo.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })
        self.assertTrue(cust.id)

    def test_04_customer_write_foreign_route_rejected(self):
        with self.assertRaises(AccessError):
            self.customer_a.with_user(self.user_a).write({'route_id': self.route_b.id})

    def test_05_customer_write_own_route_allowed(self):
        self.customer_a.with_user(self.user_a).write({'route_id': self.route_a.id})
        self.assertEqual(self.customer_a.route_id, self.route_a)

    def test_06_meter_create_subscriber_foreign_customer_rejected(self):
        with self.assertRaises(AccessError):
            self.env['utility.meter'].with_user(self.user_a).create({
                'meter_number': 'W17MI-MTR-FAIL',
                'connection_type': 'subscriber',
                'customer_id': self.customer_b.id,
                'payment_type': 'postpaid',
            })

    def test_07_meter_create_subscriber_own_customer_allowed(self):
        meter = self.env['utility.meter'].with_user(self.user_a).create({
            'meter_number': 'W17MI-MTR-OK',
            'connection_type': 'subscriber',
            'customer_id': self.customer_a.id,
            'payment_type': 'postpaid',
        })
        self.assertTrue(meter.id)

    def test_08_meter_create_not_connected_allowed(self):
        meter = self.env['utility.meter'].with_user(self.user_a).create({
            'meter_number': 'W17MI-MTR-NC',
            'connection_type': 'not_connected',
            'payment_type': 'manual',
        })
        self.assertTrue(meter.id)

    def test_09_meter_write_reassign_foreign_customer_rejected(self):
        meter = self.env['utility.meter'].with_context(utility_scope_bypass=True).create({
            'meter_number': 'W17MI-MTR-REASN',
            'connection_type': 'subscriber',
            'customer_id': self.customer_a.id,
            'payment_type': 'postpaid',
        })
        with self.assertRaises(AccessError):
            meter.with_user(self.user_a).write({'customer_id': self.customer_b.id})

    def test_10_scope_bypass_allows_cross_scope_create(self):
        partner_mig = self.env['res.partner'].create({'name': 'W17MI Mig B', 'region_id': self.region_b.id, 'area_id': self.branch_b.id})
        cust = self.env['utility.customer'].with_user(self.user_a).with_context(utility_scope_bypass=True).create({
            'partner_id': partner_mig.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })
        self.assertTrue(cust.id)
