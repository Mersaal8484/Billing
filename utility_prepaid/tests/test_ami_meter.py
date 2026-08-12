from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.utility_prepaid.controllers import ami_api


class TestPrepaidAMI(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة اختبار AMI', 'code': 'AMI-CATEGORY',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'نوع اختبار AMI', 'code': 'AMI-SUBSCRIBER',
            'category_id': cls.category.id,
        })

    def test_ami_callback_resolves_operational_number(self):
        partner = self.env['res.partner'].create({'name': 'عميل AMI'})
        meter = self.env['utility.meter'].create({
            'meter_number': 'AMI-METER-001',
            'operational_number': 'AMI-OP-001',
            'payment_type': 'postpaid',
        })
        customer = self.env['utility.customer'].create({
            'customer_number': 'AMI-CUSTOMER-001',
            'partner_id': partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'meter_id': meter.id,
        })
        meter.write({'customer_id': customer.id, 'connection_type': 'subscriber'})
        provider = self.env['utility.integration.provider'].create({
            'name': 'مزود AMI للاختبار',
            'provider_type': 'ami',
            'mode': 'manual',
            'webhook_secret': 'ami-test-secret',
            'company_id': self.env.company.id,
        })
        controller = ami_api.UtilityPrepaidAMIController()
        fake_request = SimpleNamespace(
            env=self.env,
            jsonrequest={
                'secret': provider.webhook_secret,
                'operational_number': meter.operational_number,
                'reading_value': 123.5,
            },
        )
        with patch.object(ami_api, 'request', fake_request):
            result = controller.ami_reading_callback()
        self.assertTrue(result['success'])
        reading = self.env['utility.reading'].browse(result['reading_id'])
        self.assertEqual(reading.meter_id, meter)
        self.assertEqual(reading.account_id, customer)
