from odoo.tests.common import TransactionCase


class TestPropertyManagement(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Property = self.env['property.property']
        self.Unit = self.env['property.unit']
        self.Lease = self.env['property.lease']
        self.Tenant = self.env['property.tenant']
        self.Owner = self.env['property.owner']
        self.Payment = self.env['property.payment']
        self.Maintenance = self.env['property.maintenance']

        self.company = self.env.company
        self.partner = self.env['res.partner'].create({'name': 'Test Contact'})
        self.partner2 = self.env['res.partner'].create({'name': 'Test Tenant'})

        self.property_type = self.env.ref('property_management.property_type_residential')
        self.property_status = self.env.ref('property_management.property_status_active')
        self.unit_type = self.env.ref('property_management.unit_type_apartment')
        self.unit_status = self.env.ref('property_management.unit_status_available')
        self.lease_status = self.env.ref('property_management.lease_status_active')
        self.maint_type = self.env.ref('property_management.maint_type_corrective')
        self.payment_freq = self.env.ref('property_management.payment_freq_monthly')

    def test_01_create_property(self):
        prop = self.Property.create({
            'name': 'Test Property',
            'code': 'TEST-001',
            'property_type': self.property_type.id,
            'status': self.property_status.id,
            'company_id': self.company.id,
        })
        self.assertTrue(prop.name)
        self.assertEqual(prop.code, 'TEST-001')
        self.assertTrue(prop.company_id)

    def test_02_create_unit(self):
        prop = self.Property.create({
            'name': 'Prop for Unit',
            'code': 'TEST-002',
            'property_type': self.property_type.id,
            'status': self.property_status.id,
        })
        unit = self.Unit.create({
            'property_id': prop.id,
            'number': 'A101',
            'unit_type': self.unit_type.id,
            'status': self.unit_status.id,
            'area': 100.0,
            'bedrooms': 2,
            'monthly_rent': 5000.0,
        })
        self.assertEqual(unit.number, 'A101')
        self.assertEqual(unit.area, 100.0)
        self.assertEqual(unit.monthly_rent, 5000.0)

    def test_03_create_owner(self):
        owner = self.Owner.create({
            'partner_id': self.partner.id,
            'owner_code': 'OWN-TEST',
        })
        self.assertTrue(owner.name)
        self.assertEqual(owner.owner_code, 'OWN-TEST')

    def test_04_create_tenant(self):
        tenant = self.Tenant.create({
            'partner_id': self.partner2.id,
            'tenant_code': 'TNT-TEST',
        })
        self.assertTrue(tenant.name)
        self.assertEqual(tenant.tenant_code, 'TNT-TEST')

    def test_05_create_lease(self):
        prop = self.Property.create({
            'name': 'Lease Test',
            'code': 'TEST-003',
            'property_type': self.property_type.id,
            'status': self.property_status.id,
        })
        unit = self.Unit.create({
            'property_id': prop.id,
            'number': 'B201',
            'unit_type': self.unit_type.id,
            'status': self.unit_status.id,
            'monthly_rent': 7000.0,
        })
        tenant = self.Tenant.create({
            'partner_id': self.partner2.id,
            'tenant_code': 'TNT-LEASE',
        })
        lease = self.Lease.create({
            'property_id': prop.id,
            'unit_id': unit.id,
            'tenant_id': tenant.id,
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'rent_amount': 7000.0,
            'rent_frequency': self.payment_freq.id,
        })
        self.assertEqual(lease.state, 'draft')
        self.assertEqual(lease.rent_amount, 7000.0)

    def test_06_lease_workflow(self):
        prop = self.Property.create({'name': 'WF Test', 'code': 'TEST-004',
                                     'property_type': self.property_type.id,
                                     'status': self.property_status.id})
        unit = self.Unit.create({'property_id': prop.id, 'number': 'C301',
                                 'unit_type': self.unit_type.id,
                                 'status': self.unit_status.id,
                                 'monthly_rent': 8000.0})
        tenant = self.Tenant.create({'partner_id': self.partner2.id,
                                     'tenant_code': 'TNT-WF'})
        lease = self.Lease.create({
            'property_id': prop.id, 'unit_id': unit.id, 'tenant_id': tenant.id,
            'start_date': '2024-06-01', 'end_date': '2025-05-31',
            'rent_amount': 8000.0, 'rent_frequency': self.payment_freq.id,
        })
        self.assertEqual(lease.state, 'draft')
        lease.action_review()
        self.assertEqual(lease.state, 'review')
        lease.action_activate()
        self.assertEqual(lease.state, 'active')
        self.assertTrue(lease.schedule_ids)
        lease.action_expire()
        self.assertEqual(lease.state, 'expired')

    def test_07_generate_payment_schedule(self):
        prop = self.Property.create({'name': 'PS Test', 'code': 'TEST-005',
                                     'property_type': self.property_type.id,
                                     'status': self.property_status.id})
        unit = self.Unit.create({'property_id': prop.id, 'number': 'D401',
                                 'unit_type': self.unit_type.id,
                                 'status': self.unit_status.id,
                                 'monthly_rent': 10000.0})
        tenant = self.Tenant.create({'partner_id': self.partner2.id,
                                     'tenant_code': 'TNT-PS'})
        lease = self.Lease.create({
            'property_id': prop.id, 'unit_id': unit.id, 'tenant_id': tenant.id,
            'start_date': '2024-01-01', 'end_date': '2024-03-31',
            'rent_amount': 10000.0, 'rent_frequency': self.payment_freq.id,
        })
        lease.action_generate_schedule()
        self.assertTrue(len(lease.schedule_ids) >= 3)
        total = sum(lease.schedule_ids.mapped('amount'))
        self.assertAlmostEqual(total, 30000.0, delta=100)

    def test_08_maintenance_request(self):
        prop = self.Property.create({'name': 'Maint Test', 'code': 'TEST-006',
                                     'property_type': self.property_type.id,
                                     'status': self.property_status.id})
        unit = self.Unit.create({'property_id': prop.id, 'number': 'E501',
                                 'unit_type': self.unit_type.id,
                                 'status': self.unit_status.id})
        maint = self.Maintenance.create({
            'property_id': prop.id,
            'unit_id': unit.id,
            'maintenance_type': self.maint_type.id,
            'priority': 'high',
            'description': 'Leaking pipe in bathroom',
            'parts_cost': 150.0,
            'labor_cost': 200.0,
        })
        self.assertEqual(maint.state, 'draft')
        self.assertEqual(maint.total_cost, 350.0)
        maint.action_submit()
        self.assertEqual(maint.state, 'submitted')
        maint.action_approve()
        self.assertEqual(maint.state, 'approved')
        maint.action_start()
        self.assertEqual(maint.state, 'in_progress')
        maint.action_done()
        self.assertEqual(maint.state, 'done')

    def test_09_occupancy_computation(self):
        prop = self.Property.create({'name': 'Occ Test', 'code': 'TEST-007',
                                     'property_type': self.property_type.id,
                                     'status': self.property_status.id})
        self.Unit.create({'property_id': prop.id, 'number': 'F601',
                          'unit_type': self.unit_type.id,
                          'status': self.unit_status.id})
        prop.invalidate_recordset(['total_units'])
        self.assertEqual(prop.total_units, 1)
        self.assertEqual(prop.vacant_units, 1)

    def test_10_payment_workflow(self):
        prop = self.Property.create({'name': 'Pay Test', 'code': 'TEST-008',
                                     'property_type': self.property_type.id,
                                     'status': self.property_status.id})
        unit = self.Unit.create({'property_id': prop.id, 'number': 'G701',
                                 'unit_type': self.unit_type.id,
                                 'status': self.unit_status.id,
                                 'monthly_rent': 5000.0})
        tenant = self.Tenant.create({'partner_id': self.partner2.id,
                                     'tenant_code': 'TNT-PAY'})
        lease = self.Lease.create({
            'property_id': prop.id, 'unit_id': unit.id, 'tenant_id': tenant.id,
            'start_date': '2024-01-01', 'end_date': '2024-12-31',
            'rent_amount': 5000.0, 'rent_frequency': self.payment_freq.id,
        })
        lease.action_generate_schedule()
        schedule = lease.schedule_ids[0]
        payment = self.Payment.create({
            'schedule_id': schedule.id,
            'lease_id': lease.id,
            'tenant_id': tenant.id,
            'unit_id': unit.id,
            'amount': 5000.0,
            'received_amount': 5000.0,
        })
        self.assertEqual(payment.state, 'draft')
        payment.action_confirm()
        self.assertEqual(payment.state, 'confirmed')
        payment.action_paid()
        self.assertEqual(payment.state, 'paid')
        self.assertEqual(schedule.state, 'paid')

    def test_11_payment_exchange_rate_override(self):
        prop = self.Property.create({'name': 'Rate Test', 'code': 'TEST-009',
                                     'property_type': self.property_type.id,
                                     'status': self.property_status.id})
        unit = self.Unit.create({'property_id': prop.id, 'number': 'H801',
                                 'unit_type': self.unit_type.id,
                                 'status': self.unit_status.id,
                                 'monthly_rent': 100.0})
        tenant = self.Tenant.create({'partner_id': self.partner2.id,
                                     'tenant_code': 'TNT-RATE'})
        lease = self.Lease.create({
            'property_id': prop.id, 'unit_id': unit.id, 'tenant_id': tenant.id,
            'start_date': '2024-01-01', 'end_date': '2024-12-31',
            'rent_amount': 100.0, 'rent_frequency': self.payment_freq.id,
        })
        lease.action_generate_schedule()
        schedule = lease.schedule_ids[0]
        payment = self.Payment.create({
            'schedule_id': schedule.id,
            'lease_id': lease.id,
            'tenant_id': tenant.id,
            'unit_id': unit.id,
            'amount': 100.0,
            'received_amount': 100.0,
            'override_exchange_rate': True,
            'exchange_rate': 600.0,
        })
        self.assertEqual(payment.company_amount, 60000.0)
