from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestUtilityCustomerWizardMeterOnboarding(TransactionCase):
    """Subscriber onboarding: operational_number is the logical meter
    identifier, serial_number is never collected in the Core wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.region = cls.env['utility.region'].create({
            'name': 'منطقة معالج العداد', 'code': 'WZ-REG', 'type': 'region',
        })
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة معالج', 'code': 'WZ-CAT',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'نوع معالج', 'code': 'WZ-SUB',
            'category_id': cls.category.id,
        })
        cls.template = cls.env['utility.contract.template'].create({
            'name': 'عقد معالج', 'code': 'WZ-TMP', 'scope': 'global',
            'subscriber_category_ids': [(6, 0, [cls.category.id])],
            'subscriber_ids': [(6, 0, [cls.subscriber.id])],
        })

    def _new_wizard(self, operational_number='OP-1', meter_number='WZ-MTR-1'):
        return self.env['utility.customer.wizard'].create({
            'name': 'مشترك معالج اختبار',
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'contract_template_id': self.template.id,
            'payment_type': 'postpaid',
            'utility_region_id': self.region.id,
            'create_meter': True,
            'meter_number': meter_number,
            'operational_number': operational_number,
        })

    def test_wizard_rejects_new_meter_without_operational_number(self):
        wizard = self._new_wizard(operational_number='')
        with self.assertRaises(ValidationError) as ctx:
            wizard.action_create_customer()
        self.assertIn('الرقم التشغيلي للعداد مطلوب', str(ctx.exception))

    def test_wizard_rejects_blank_operational_number(self):
        wizard = self._new_wizard(operational_number='   ')
        with self.assertRaises(ValidationError):
            wizard.action_create_customer()

    def test_wizard_accepts_operational_number_without_serial(self):
        wizard = self._new_wizard(operational_number='OP-458721')
        result = wizard.action_create_customer()
        customer = self.env['utility.customer'].browse(result['res_id'])
        meter = customer.meter_id
        self.assertTrue(meter)
        self.assertEqual(meter.operational_number, 'OP-458721')
        self.assertEqual(meter.connection_type, 'subscriber')
        self.assertEqual(meter.customer_id, customer)
        self.assertEqual(meter.region_id, self.region)

    def test_core_wizard_has_no_serial_input(self):
        fields = self.env['utility.customer.wizard']._fields
        # Core must never collect the physical serial or technical product
        # specs; those belong to Inventory/Product.
        self.assertNotIn('serial_number', fields)
        self.assertNotIn('manufacturer', fields)
        self.assertNotIn('voltage', fields)
        self.assertNotIn('current_rating', fields)
        self.assertNotIn('power_rating', fields)

    def test_core_wizard_requests_logical_meter_fields_only(self):
        # The Core wizard exposes create_meter/metre_number/operational_number
        # as the logical subscriber onboarding fields. stock.lot selection
        # (if present) is an Inventory extension, never a Core serial text.
        self.assertIn('create_meter', self.env['utility.customer.wizard']._fields)
        self.assertIn('meter_number', self.env['utility.customer.wizard']._fields)
        self.assertIn('operational_number', self.env['utility.customer.wizard']._fields)

    def test_meter_connection_type_inference_and_onchange(self):
        """Meters auto-infer subscriber connection_type when customer is written and clear on not_connected."""
        wizard = self._new_wizard(operational_number='OP-INFER-01')
        res = wizard.action_create_customer()
        customer = self.env['utility.customer'].browse(res['res_id'])
        meter = customer.meter_id
        self.assertEqual(meter.connection_type, 'subscriber')

        # Unlink via connection_type = 'not_connected' clears customer_id
        meter.write({'connection_type': 'not_connected'})
        self.assertEqual(meter.connection_type, 'not_connected')
        self.assertFalse(meter.customer_id)

        # Write customer_id again -> auto-infers connection_type = 'subscriber'
        meter.write({'customer_id': customer.id})
        self.assertEqual(meter.connection_type, 'subscriber')
        self.assertEqual(meter.customer_id, customer)