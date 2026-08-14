from odoo.tests.common import TransactionCase


class TestOrganizationalScopeBilling(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company

        self.region_sanaa = self.env['utility.region'].create({
            'name': 'منطقة صنعاء Billing',
            'code': 'REG_SANAA_BILL',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.branch_sanaa1 = self.env['utility.region'].create({
            'name': 'فرع التحرير Billing',
            'code': 'AREA_TAHREER_BILL',
            'type': 'area',
            'parent_id': self.region_sanaa.id,
            'company_id': self.company.id,
        })
        self.region_aden = self.env['utility.region'].create({
            'name': 'منطقة عدن Billing',
            'code': 'REG_ADEN_BILL',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.branch_aden1 = self.env['utility.region'].create({
            'name': 'فرع كريتر Billing',
            'code': 'AREA_CRATER_BILL',
            'type': 'area',
            'parent_id': self.region_aden.id,
            'company_id': self.company.id,
        })

        self.partner_sanaa = self.env['res.partner'].create({
            'name': 'مشترك صنعاء Billing',
            'region_id': self.region_sanaa.id,
            'area_id': self.branch_sanaa1.id,
            'company_id': self.company.id,
        })
        self.partner_aden = self.env['res.partner'].create({
            'name': 'مشترك عدن Billing',
            'region_id': self.region_aden.id,
            'area_id': self.branch_aden1.id,
            'company_id': self.company.id,
        })

        self.customer_sanaa = self.env['utility.customer'].create({
            'name': 'حساب صنعاء 02',
            'partner_id': self.partner_sanaa.id,
            'customer_number': 'CUST_SANAA_BILL_02',
            'company_id': self.company.id,
        })
        self.customer_aden = self.env['utility.customer'].create({
            'name': 'حساب عدن 02',
            'partner_id': self.partner_aden.id,
            'customer_number': 'CUST_ADEN_BILL_02',
            'company_id': self.company.id,
        })

        # Utility Bill (Sale Order with account_id)
        self.bill_sanaa = self.env['sale.order'].create({
            'partner_id': self.partner_sanaa.id,
            'account_id': self.customer_sanaa.id,
            'company_id': self.company.id,
        })
        self.bill_aden = self.env['sale.order'].create({
            'partner_id': self.partner_aden.id,
            'account_id': self.customer_aden.id,
            'company_id': self.company.id,
        })

        self.user_billing_sanaa = self.env['res.users'].create({
            'name': 'فوترة صنعاء',
            'login': 'bill_sanaa_user',
            'email': 'bill_sanaa@billing.local',
            'scope_mode': 'restricted',
            'assigned_region_ids': [(6, 0, [self.region_sanaa.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_billing_manager').id])],
        })

    def test_01_utility_bill_isolation(self):
        """Restricted Billing user in Sanaa sees Sanaa Utility Bill, not Aden Utility Bill."""
        bills = self.env['sale.order'].with_user(self.user_billing_sanaa).search([('account_id', '!=', False)])
        self.assertIn(self.bill_sanaa, bills)
        self.assertNotIn(self.bill_aden, bills)
