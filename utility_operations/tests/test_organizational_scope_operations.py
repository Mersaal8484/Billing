from odoo.tests.common import TransactionCase


class TestOrganizationalScopeOperations(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company

        self.region_sanaa = self.env['utility.region'].create({
            'name': 'منطقة صنعاء Operations',
            'code': 'REG_SANAA_OPS',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.branch_sanaa1 = self.env['utility.region'].create({
            'name': 'فرع السبعين',
            'code': 'AREA_SABEEN',
            'type': 'area',
            'parent_id': self.region_sanaa.id,
            'company_id': self.company.id,
        })
        self.region_aden = self.env['utility.region'].create({
            'name': 'منطقة عدن Operations',
            'code': 'REG_ADEN_OPS',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.branch_aden1 = self.env['utility.region'].create({
            'name': 'فرع المنصورة',
            'code': 'AREA_MANSOURA',
            'type': 'area',
            'parent_id': self.region_aden.id,
            'company_id': self.company.id,
        })

        self.partner_sanaa = self.env['res.partner'].create({
            'name': 'مشترك السبعين',
            'region_id': self.region_sanaa.id,
            'area_id': self.branch_sanaa1.id,
            'company_id': self.company.id,
        })
        self.partner_aden = self.env['res.partner'].create({
            'name': 'مشترك المنصورة',
            'region_id': self.region_aden.id,
            'area_id': self.branch_aden1.id,
            'company_id': self.company.id,
        })

        self.customer_sanaa = self.env['utility.customer'].create({
            'name': 'حساب السبعين 01',
            'partner_id': self.partner_sanaa.id,
            'customer_number': 'CUST_SABEEN_01',
            'company_id': self.company.id,
        })
        self.customer_aden = self.env['utility.customer'].create({
            'name': 'حساب المنصورة 01',
            'partner_id': self.partner_aden.id,
            'customer_number': 'CUST_MANSOURA_01',
            'company_id': self.company.id,
        })

        self.service_order_sanaa = self.env['utility.service.order'].create({
            'customer_id': self.customer_sanaa.id,
            'order_type': 'new_connection',
            'company_id': self.company.id,
        })
        self.service_order_aden = self.env['utility.service.order'].create({
            'customer_id': self.customer_aden.id,
            'order_type': 'new_connection',
            'company_id': self.company.id,
        })

        self.user_sanaa = self.env['res.users'].create({
            'name': 'فني صنعاء',
            'login': 'tech_sanaa_ops',
            'email': 'tech_sanaa@ops.local',
            'scope_mode': 'restricted',
            'assigned_region_ids': [(6, 0, [self.region_sanaa.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_technician').id])],
        })

    def test_01_service_order_isolation(self):
        """Restricted user in Sanaa sees only Sanaa Service Order, not Aden."""
        orders = self.env['utility.service.order'].with_user(self.user_sanaa).search([])
        self.assertIn(self.service_order_sanaa, orders)
        self.assertNotIn(self.service_order_aden, orders)
