from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase


class TestCustomerMobileAndMeterOperationalNumber(TransactionCase):

    def test_operational_number_is_normalized_and_searchable(self):
        meter = self.env['utility.meter'].create({
            'meter_number': 'OPS-METER-001',
            'operational_number': '  OP-001  ',
        })
        self.assertEqual(meter.operational_number, 'OP-001')
        self.assertIn('[OP-001] OPS-METER-001', meter.display_name)
        self.assertIn(meter.id, self.env['utility.meter']._name_search('OP-001'))
        meter.write({'operational_number': '   '})
        self.assertFalse(meter.operational_number)

    def test_operational_number_is_unique_per_company(self):
        self.env['utility.meter'].create({
            'meter_number': 'OPS-METER-002',
            'operational_number': 'OP-002',
        })
        with self.assertRaises(IntegrityError):
            self.env['utility.meter'].create({
                'meter_number': 'OPS-METER-003',
                'operational_number': 'OP-002',
            })

    def test_sms_without_mobile_fails_with_explicit_code(self):
        notification = self.env['utility.notification.log'].create({
            'name': 'اختبار SMS',
            'channel': 'sms',
            'event_type': 'invoice_created',
            'body': 'رسالة اختبار',
        })
        notification.action_dispatch()
        self.assertEqual(notification.state, 'failed')
        self.assertIn('CUSTOMER_MOBILE_REQUIRED', notification.error_message)
