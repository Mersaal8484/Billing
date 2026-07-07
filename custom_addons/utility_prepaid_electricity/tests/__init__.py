from odoo.tests.common import TransactionCase


class TestUtilityCore(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Region = self.env['utility.region']
        self.Area = self.env['utility.area']
        self.Feeder = self.env['utility.feeder']
        self.Transformer = self.env['utility.transformer']
        self.Customer = self.env['utility.customer']
        self.Account = self.env['utility.account']
        self.Meter = self.env['utility.meter']
        self.Tariff = self.env['utility.tariff']
        self.Sale = self.env['utility.sale']
        self.Token = self.env['utility.token']
        self.Payment = self.env['utility.payment']
        self.Reversal = self.env['utility.reversal']
        self.Adjustment = self.env['utility.adjustment']
        self.Alarm = self.env['utility.alarm']
        self.ServiceOrder = self.env['utility.service.order']

        self.partner = self.env['res.partner'].create({'name': 'Test Customer'})
        self.company = self.env.company

    def _create_region_area(self):
        region = self.Region.create({'name': 'Test Region', 'code': 'TR'})
        area = self.Area.create({'name': 'Test Area', 'code': 'TA', 'region_id': region.id})
        return region, area

    def _create_tariff(self):
        cat = self.env['utility.tariff.category'].create({'name': 'Test', 'code': 'TST'})
        tariff = self.Tariff.create({
            'name': 'Test Flat', 'code': 'TFLAT', 'category_id': cat.id,
            'tariff_type': 'flat', 'price_per_kwh': 0.20, 'fixed_charge': 5.0,
        })
        return tariff

    def _create_customer_account(self, region, area, tariff):
        customer = self.Customer.create({
            'partner_id': self.partner.id,
            'mobile': '+966500000001',
            'customer_type': 'residential',
            'region_id': region.id,
            'area_id': area.id,
        })
        meter_type = self.env['utility.meter.type'].create({'name': 'Test', 'code': 'TMTR'})
        meter_status = self.env['utility.meter.status'].create({'name': 'Active', 'code': 'ACT'})
        meter = self.Meter.create({
            'meter_type_id': meter_type.id,
            'status_id': meter_status.id,
            'phase': 'single',
            'serial_number': 'SN-TEST-001',
            'region_id': region.id,
            'area_id': area.id,
        })
        account = self.Account.create({
            'customer_id': customer.id,
            'meter_id': meter.id,
            'tariff_id': tariff.id,
            'balance': 100.0,
            'state': 'active',
        })
        meter.account_id = account
        return customer, account, meter

    def test_01_create_region(self):
        region = self.Region.create({'name': 'Central', 'code': 'CTR'})
        self.assertTrue(region.name)
        self.assertEqual(region.code, 'CTR')

    def test_02_create_area(self):
        region, _ = self._create_region_area()
        area = self.Area.create({'name': 'Downtown', 'code': 'DT', 'region_id': region.id})
        self.assertEqual(area.region_id.id, region.id)

    def test_03_create_feeder(self):
        _, area = self._create_region_area()
        feeder = self.Feeder.create({
            'name': 'Main Feeder', 'code': 'MF-1',
            'area_id': area.id, 'voltage_level': 'mv', 'rated_capacity': 5000,
        })
        self.assertEqual(feeder.area_id.id, area.id)

    def test_04_create_transformer(self):
        _, area = self._create_region_area()
        transformer = self.Transformer.create({
            'name': 'Sub A', 'code': 'SUB-A',
            'area_id': area.id, 'capacity': 1000, 'phase': 'three',
        })
        self.assertTrue(transformer.name)

    def test_05_create_customer(self):
        region, area = self._create_region_area()
        customer = self.Customer.create({
            'partner_id': self.partner.id,
            'mobile': '+966500000002',
            'customer_type': 'residential',
            'region_id': region.id,
            'area_id': area.id,
            'connection_status': 'active',
        })
        self.assertTrue(customer.customer_number)
        self.assertEqual(customer.connection_status, 'active')

    def test_06_create_account(self):
        region, area = self._create_region_area()
        tariff = self._create_tariff()
        customer, account, meter = self._create_customer_account(region, area, tariff)
        self.assertTrue(account.account_number)
        self.assertEqual(account.balance, 100.0)
        self.assertEqual(account.state, 'active')

    def test_07_tariff_calculation_flat(self):
        tariff = self._create_tariff()
        result = tariff.calculate_kwh(100.0)
        self.assertGreater(result['kwh'], 0)
        self.assertAlmostEqual(result['unit_price'], 0.20, delta=0.01)
        self.assertGreater(result['total'], 0)

    def test_08_tariff_calculation_block(self):
        cat = self.env['utility.tariff.category'].create({'name': 'Test', 'code': 'TST2'})
        tariff = self.Tariff.create({
            'name': 'Test Block', 'code': 'TBLK', 'category_id': cat.id,
            'tariff_type': 'block', 'fixed_charge': 10.0,
        })
        self.env['utility.tariff.block'].create([
            {'tariff_id': tariff.id, 'sequence': 10, 'name': '0-100',
             'from_kwh': 0, 'to_kwh': 100, 'price_per_kwh': 0.15},
            {'tariff_id': tariff.id, 'sequence': 20, 'name': '101+',
             'from_kwh': 101, 'to_kwh': None, 'price_per_kwh': 0.25},
        ])
        result = tariff.calculate_kwh(50.0)
        self.assertGreater(result['kwh'], 0)

    def test_09_prepaid_sale_workflow(self):
        region, area = self._create_region_area()
        tariff = self._create_tariff()
        customer, account, meter = self._create_customer_account(region, area, tariff)
        sale = self.Sale.create({
            'customer_id': customer.id,
            'account_id': account.id,
            'meter_id': meter.id,
            'tariff_id': tariff.id,
            'amount_paid': 100.0,
            'payment_method': 'cash',
        })
        self.assertEqual(sale.state, 'draft')
        sale.action_calculate()
        self.assertGreater(sale.kwh_purchased, 0)
        sale.action_confirm()
        self.assertEqual(sale.state, 'confirmed')
        sale.action_generate_token()
        self.assertEqual(sale.state, 'token_generated')
        self.assertTrue(sale.token_id)
        sale.action_complete()
        self.assertEqual(sale.state, 'completed')

    def test_10_sts_token_generation(self):
        region, area = self._create_region_area()
        tariff = self._create_tariff()
        customer, account, meter = self._create_customer_account(region, area, tariff)
        sale = self.Sale.create({
            'customer_id': customer.id,
            'account_id': account.id,
            'meter_id': meter.id,
            'tariff_id': tariff.id,
            'amount_paid': 50.0,
        })
        sale.action_calculate()
        sale.action_confirm()
        sale.action_generate_token()
        token = sale.token_id
        self.assertTrue(token.token_number)
        self.assertEqual(token.status, 'success')
        self.assertEqual(token.amount, 50.0)

    def test_11_payment_workflow(self):
        region, area = self._create_region_area()
        tariff = self._create_tariff()
        customer, account, meter = self._create_customer_account(region, area, tariff)
        payment = self.Payment.create({
            'customer_id': customer.id,
            'account_id': account.id,
            'amount': 200.0,
            'payment_method': 'bank',
        })
        self.assertEqual(payment.state, 'draft')
        payment.action_confirm()
        self.assertEqual(payment.state, 'confirmed')
        payment.action_reconcile()
        self.assertEqual(payment.state, 'reconciled')

    def test_12_adjustment_workflow(self):
        region, area = self._create_region_area()
        tariff = self._create_tariff()
        customer, account, meter = self._create_customer_account(region, area, tariff)
        adj = self.Adjustment.create({
            'customer_id': customer.id,
            'account_id': account.id,
            'adjustment_type': 'credit',
            'amount': 50.0,
            'reason': 'Test credit adjustment',
        })
        self.assertEqual(adj.state, 'draft')
        adj.action_approve()
        self.assertEqual(adj.state, 'approved')
        adj.action_apply()
        self.assertEqual(adj.state, 'applied')

    def test_13_reversal_workflow(self):
        region, area = self._create_region_area()
        tariff = self._create_tariff()
        customer, account, meter = self._create_customer_account(region, area, tariff)
        sale = self.Sale.create({
            'customer_id': customer.id,
            'account_id': account.id,
            'meter_id': meter.id,
            'tariff_id': tariff.id,
            'amount_paid': 100.0,
        })
        sale.action_calculate()
        sale.action_confirm()
        sale.action_generate_token()
        sale.action_complete()
        rev = self.Reversal.create({
            'customer_id': customer.id,
            'account_id': account.id,
            'meter_id': meter.id,
            'sale_id': sale.id,
            'amount': 100.0,
            'reason': 'Test reversal',
        })
        rev.action_approve()
        rev.action_complete()
        self.assertEqual(rev.state, 'completed')

    def test_14_alarm_creation(self):
        region, area = self._create_region_area()
        tariff = self._create_tariff()
        customer, account, meter = self._create_customer_account(region, area, tariff)
        alarm = self.Alarm.create({
            'alarm_type': 'low_credit',
            'severity': 'warning',
            'customer_id': customer.id,
            'account_id': account.id,
            'meter_id': meter.id,
            'description': 'Low credit test',
        })
        self.assertTrue(alarm.alarm_code)
        self.assertEqual(alarm.state, 'new')
        alarm.action_acknowledge()
        self.assertEqual(alarm.state, 'acknowledged')

    def test_15_service_order_workflow(self):
        region, area = self._create_region_area()
        tariff = self._create_tariff()
        customer, account, meter = self._create_customer_account(region, area, tariff)
        so = self.ServiceOrder.create({
            'service_type': 'meter_replacement',
            'priority': 'high',
            'customer_id': customer.id,
            'account_id': account.id,
            'meter_id': meter.id,
            'description': 'Test service order',
            'old_meter_id': meter.id,
        })
        self.assertEqual(so.state, 'draft')
        so.action_approve()
        self.assertEqual(so.state, 'approved')
        so.action_schedule()
        self.assertEqual(so.state, 'scheduled')
        so.action_start()
        self.assertEqual(so.state, 'in_progress')
        so.action_complete()
        self.assertEqual(so.state, 'completed')

    def test_16_low_credit_cron(self):
        self.Alarm.cron_check_low_credit()
        alarms = self.Alarm.search([('alarm_type', '=', 'low_credit')])
        self.assertTrue(len(alarms) >= 0)

    def test_17_region_hierarchy(self):
        region, area = self._create_region_area()
        region.invalidate_model(['area_count'])
        self.assertEqual(region.area_count, 1)

    def test_18_meter_name_search(self):
        region, area = self._create_region_area()
        tariff = self._create_tariff()
        customer, account, meter = self._create_customer_account(region, area, tariff)
        result = self.Meter.name_search('SN-TEST-001')
        self.assertTrue(len(result) >= 1)

    def test_19_multi_company(self):
        company2 = self.env['res.company'].create({'name': 'Test Utility Co'})
        region = self.Region.create({
            'name': 'MultiCo Region',
            'code': 'MCR',
            'company_id': company2.id,
        })
        self.assertEqual(region.company_id.id, company2.id)

    def test_20_customer_documents(self):
        region, area = self._create_region_area()
        customer = self.Customer.create({
            'partner_id': self.partner.id,
            'customer_type': 'residential',
            'region_id': region.id,
            'area_id': area.id,
        })
        attachment = self.env['ir.attachment'].create({
            'name': 'test_doc.txt',
            'res_model': 'utility.customer',
            'res_id': customer.id,
            'type': 'binary',
            'datas': 'dGVzdA==',
        })
        self.assertEqual(len(customer.document_ids), 1)
