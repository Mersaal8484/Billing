from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestUtilityCustomerLifecycle(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.region = cls.env['utility.region'].create({
            'name': 'منطقة دورة الحياة', 'code': 'LIFE-REGION', 'type': 'region',
        })
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة دورة الحياة', 'code': 'LIFE-CATEGORY',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'نوع دورة الحياة', 'category_id': cls.category.id,
        })

    def _customer(self, suffix, meter_number):
        partner = self.env['res.partner'].create({
            'name': 'عميل دورة الحياة %s' % suffix,
            'region_id': self.region.id,
        })
        meter = self.env['utility.meter'].create({
            'meter_number': meter_number,
            'connection_type': 'subscriber',
            'payment_type': 'postpaid',
            'active': True,
        })
        return self.env['utility.customer'].create({
            'customer_number': 'LIFE-%s' % suffix,
            'partner_id': partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'meter_id': meter.id,
        })

    def test_state_machine_is_controlled(self):
        customer = self._customer('001', 'LIFE-METER-001')
        with self.assertRaises(ValidationError):
            customer.write({'state': 'active'})

        customer.action_activate()
        self.assertEqual(customer.state, 'active')
        self.assertEqual(customer.current_meter_assignment_id.meter_id, customer.meter_id)

        customer.action_suspend('مراجعة بيانات')
        self.assertEqual(customer.state, 'suspended')
        customer.action_reactivate('اكتملت المراجعة')
        self.assertEqual(customer.state, 'active')
        customer.with_context(lifecycle_override=True).action_disconnect('طلب إداري')
        self.assertEqual(customer.state, 'disconnected')
        customer.with_context(lifecycle_override=True).action_reconnect('تمت الموافقة')
        self.assertEqual(customer.state, 'active')
        customer.action_close('إغلاق الحساب')
        self.assertEqual(customer.state, 'closed')

    def test_meter_cannot_be_active_on_two_accounts(self):
        first = self._customer('002', 'LIFE-METER-002')
        first.action_activate()
        second = self.env['utility.customer'].create({
            'customer_number': 'LIFE-003',
            'partner_id': self.env['res.partner'].create({
                'name': 'حساب ثان', 'region_id': self.region.id,
            }).id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'meter_id': first.meter_id.id,
        })
        with self.assertRaises(ValidationError):
            second.action_activate()

    def test_closing_does_not_cancel_accounting_obligation(self):
        customer = self._customer('004', 'LIFE-METER-004')
        customer.action_activate()
        customer.action_close('إغلاق نهائي')
        self.assertEqual(customer.state, 'closed')
        self.assertTrue(customer.partner_id)
