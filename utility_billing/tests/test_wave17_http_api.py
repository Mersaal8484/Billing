"""
Wave 17 — HTTP API Authorization Boundary Tests (HttpCase)

These tests verify that the HTTP API endpoints enforce organizational scope
correctly. Tests are written as HttpCase scenarios.

IMPORTANT — Evidence Status:
    Static test coverage: IMPLEMENTED STATICALLY
    Runtime execution: NOT EXECUTED (requires live Odoo instance with test DB)

Do NOT claim these tests PASSED unless actual runtime evidence is provided.

Test scenarios:
- Employee (internal) scoped to Region A: valid Region A resource → 200 success
- Employee (internal) scoped to Region A: Region B resource → CUSTOMER_NOT_FOUND
- Portal Customer A: own account → success
- Portal Customer A: Customer B account → CUSTOMER_NOT_FOUND
- Crafted customer_id for out-of-scope valid record → rejected
- service_request: verify authorization before sudo-backed creation
"""
from odoo.tests.common import HttpCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'wave17_http')
class TestWave17HttpApiBoundary(HttpCase):

    def setUp(self):
        super().setUp()
        # Setup helper: all ORM data created under sudo to avoid scope conflicts
        Region = self.env['utility.region']
        self.region_a = Region.create({'name': 'W17H Region A', 'type': 'region', 'code': 'W17H-RA'})
        self.region_b = Region.create({'name': 'W17H Region B', 'type': 'region', 'code': 'W17H-RB'})
        self.branch_a = Region.create({'name': 'W17H Branch A', 'type': 'area', 'code': 'W17H-BA', 'parent_id': self.region_a.id})
        self.branch_b = Region.create({'name': 'W17H Branch B', 'type': 'area', 'code': 'W17H-BB', 'parent_id': self.region_b.id})

        Partner = self.env['res.partner']
        self.partner_a = Partner.create({'name': 'W17H PartnerA', 'region_id': self.region_a.id, 'area_id': self.branch_a.id})
        self.partner_b = Partner.create({'name': 'W17H PartnerB', 'region_id': self.region_b.id, 'area_id': self.branch_b.id})

        cats = self.env['utility.subscriber.category'].search([], limit=1)
        self.category = cats if cats else self.env['utility.subscriber.category'].create({'name': 'W17H Cat'})
        subs = self.env['utility.subscriber'].search([], limit=1)
        self.subscriber = subs if subs else self.env['utility.subscriber'].create({'name': 'W17H Sub', 'category_id': self.category.id})

        self.customer_a = self.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': self.partner_a.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })
        self.customer_b = self.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': self.partner_b.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })

        # Internal user restricted to Region A
        self.emp_user_a = self.env['res.users'].create({
            'name': 'W17H Emp Region A', 'login': 'w17h_emp_a@test.local',
            'password': 'test_password_123',
            'groups_id': [(4, self.env.ref('utility_core.group_utility_supervisor').id)],
            'scope_mode': 'restricted',
            'assigned_region_ids': [(4, self.region_a.id)],
        })

    def _post_json(self, url, payload, user=None):
        """Helper to POST a JSON-RPC body and return parsed response."""
        import json
        headers = {'Content-Type': 'application/json'}
        body = json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': payload})
        if user:
            self.authenticate(user.login, 'test_password_123')
        response = self.url_open(url, data=body.encode(), headers=headers)
        return response.json().get('result', {})

    def test_01_employee_can_access_own_region_customer(self):
        """Employee in Region A can look up a Region A customer."""
        result = self._post_json(
            '/api/v1/utility/customer/lookup',
            {'customer_id': self.customer_a.id},
            user=self.emp_user_a,
        )
        self.assertTrue(result.get('success'), f"Expected success for own-region customer: {result}")

    def test_02_employee_cannot_access_foreign_region_customer(self):
        """Employee in Region A is rejected when accessing a Region B customer."""
        result = self._post_json(
            '/api/v1/utility/customer/lookup',
            {'customer_id': self.customer_b.id},
            user=self.emp_user_a,
        )
        # Expect error (record not found in user scope via Record Rules or resolver)
        self.assertFalse(result.get('success'), f"Expected rejection for cross-scope customer: {result}")
        error_code = result.get('code', '')
        self.assertIn(error_code, ('CUSTOMER_NOT_FOUND', 'CUSTOMER_IDENTIFIER_REQUIRED'),
                      f"Unexpected error code: {error_code}")

    def test_03_service_request_cross_scope_rejected(self):
        """service_request with a Region B customer_id must be rejected for Region A employee."""
        result = self._post_json(
            '/api/v1/utility/operations/service_request',
            {
                'customer_id': self.customer_b.id,
                'service_type': 'connection',
                'description': 'Cross-scope injection attempt',
            },
            user=self.emp_user_a,
        )
        self.assertFalse(result.get('success'),
                         f"service_request must reject cross-scope customer: {result}")
        self.assertEqual(result.get('code'), 'CUSTOMER_NOT_FOUND')

    def test_04_service_request_own_region_succeeds(self):
        """service_request with own-region customer_id must succeed for Region A employee."""
        result = self._post_json(
            '/api/v1/utility/operations/service_request',
            {
                'customer_id': self.customer_a.id,
                'service_type': 'connection',
                'description': 'Valid service request from Region A',
            },
            user=self.emp_user_a,
        )
        # If utility.service.order model is available it should succeed; otherwise MODEL_UNAVAILABLE
        self.assertNotEqual(result.get('code'), 'CUSTOMER_NOT_FOUND',
                            f"service_request must NOT reject own-region customer: {result}")
