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
            'name': 'نوع دورة الحياة', 'code': 'LIFE-SUB',
            'category_id': cls.category.id,
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

    def _meter(self, meter_number):
        return self.env['utility.meter'].create({
            'meter_number': meter_number,
            'connection_type': 'subscriber',
            'payment_type': 'postpaid',
            'active': True,
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
        customer.action_close('إغلاق الحساب', final_reading=1200.0)
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

    def test_duplicate_open_assignment_is_rejected(self):
        customer = self._customer('003', 'LIFE-METER-003')
        customer.action_activate()
        self.assertTrue(customer.current_meter_assignment_id)
        other_meter = self._meter('LIFE-METER-003B')
        with self.assertRaises(ValidationError):
            self.env['utility.customer.meter.assignment'].create({
                'customer_id': customer.id,
                'meter_id': other_meter.id,
                'company_id': customer.company_id.id,
                'assignment_type': 'replacement',
            })

    def test_close_requires_final_reading(self):
        customer = self._customer('004', 'LIFE-METER-004')
        customer.action_activate()
        self.assertFalse(customer.meter_id.last_read_date)
        with self.assertRaises(ValidationError):
            customer.action_close('إغلاق نهائي')

    def test_close_closes_assignment_releases_meter_and_logs_events(self):
        customer = self._customer('005', 'LIFE-METER-005')
        customer.action_activate()
        meter = customer.meter_id
        assignment = customer.current_meter_assignment_id
        self.assertEqual(assignment.state, 'open')

        customer.action_close('إغلاق نهائي', final_reading=1500.0)

        self.assertEqual(customer.state, 'closed')
        self.assertFalse(customer.meter_id)
        self.assertFalse(customer.current_meter_assignment_id)
        self.assertFalse(meter.customer_id)
        self.assertEqual(meter.connection_type, 'not_connected')
        self.assertEqual(assignment.state, 'closed')
        self.assertAlmostEqual(assignment.final_reading, 1500.0, places=3)
        self.assertTrue(assignment.date_to)
        event_types = customer.lifecycle_event_ids.mapped('event_type')
        self.assertIn('meter_removed', event_types)
        self.assertIn('closed', event_types)

    def test_close_with_field_removal_requires_completed_service_order(self):
        customer = self._customer('006', 'LIFE-METER-006')
        customer.action_activate()
        with self.assertRaises(ValidationError):
            customer.action_close('إغلاق نهائي', final_reading=100.0,
                                  require_field_removal=True)
        customer.with_context(lifecycle_override=True).action_close(
            'إغلاق نهائي', final_reading=100.0, require_field_removal=True)
        self.assertEqual(customer.state, 'closed')

    def test_close_uses_recorded_reading_when_no_explicit_reading(self):
        customer = self._customer('007', 'LIFE-METER-007')
        customer.action_activate()
        meter = customer.meter_id
        meter.last_read_date = '2026-08-31 12:00:00'
        meter.last_reading_value = 2750.0

        customer.action_close('إغلاق نهائي')

        self.assertEqual(customer.state, 'closed')
        assignment = customer.meter_assignment_ids.filtered(
            lambda a: a.meter_id == meter)
        self.assertEqual(assignment.state, 'closed')
        self.assertAlmostEqual(assignment.final_reading, 2750.0, places=3)

    def test_closing_does_not_cancel_accounting_obligation(self):
        customer = self._customer('008', 'LIFE-METER-008')
        customer.action_activate()
        customer.action_close('إغلاق نهائي', final_reading=500.0)
        self.assertEqual(customer.state, 'closed')
        self.assertTrue(customer.partner_id)
