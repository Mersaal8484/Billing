from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo import fields
from datetime import timedelta


class TestReadingLifecycleHardening(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Reading = self.env['utility.reading']
        self.Customer = self.env['utility.customer']
        self.Meter = self.env['utility.meter']
        self.Region = self.env['utility.region']
        self.Category = self.env['utility.subscriber.category']
        self.Subscriber = self.env['utility.subscriber']
        self.Partner = self.env['res.partner']
        self.DateRange = self.env['date.range']
        self.DateRangeType = self.env['date.range.type']
        self.Staff = self.env['utility.staff']
        self.User = self.env['res.users']

        # Setup geography and period
        self.region = self.Region.create({
            'name': 'منطقة قراءات تجريبية',
            'code': 'READ-REG-01',
            'type': 'region',
            'recurring_rule_type': 'monthly',
        })
        self.area = self.Region.create({
            'name': 'فرع قراءات تجريبي',
            'code': 'READ-AREA-01',
            'type': 'area',
            'parent_id': self.region.id,
            'recurring_rule_type': 'monthly',
        })
        self.range_type = self.DateRangeType.create({
            'name': 'نوع فترة قراءات',
            'work_type': 'readings',
            'billing_period': 'monthly',
        })
        self.date_range = self.DateRange.create({
            'name': 'فترة قراءات 2026-08',
            'type_id': self.range_type.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'work_type': 'readings',
            'billing_period': 'monthly',
            'billing_cadence': 'monthly',
            'period_role': 'reading',
            'is_current_period': True,
            'state': 'open',
            'region_ids': [(4, self.region.id)],
        })

        # Setup customer & meter
        self.category = self.Category.create({'name': 'سكني', 'code': 'RES-01'})
        self.subscriber = self.Subscriber.create({'name': 'عادي', 'code': 'NORM-01', 'category_id': self.category.id})
        self.partner = self.Partner.create({'name': 'مشترك اختبار القراءات', 'region_id': self.region.id})
        self.customer = self.Customer.create({
            'customer_number': 'CUST-RD-001',
            'partner_id': self.partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'region_id': self.region.id,
            'area_id': self.area.id,
        })
        self.meter = self.Meter.create({
            'meter_number': 'MTR-RD-001',
            'customer_id': self.customer.id,
            'multiplier': 1.0,
        })

        # Setup users: Reader, Supervisor, Billing Manager
        self.role_reader = self.env.ref('utility_core.role_meter_reader')
        self.role_supervisor = self.env.ref('utility_core.role_supervisor')
        self.role_billing_mgr = self.env.ref('utility_core.role_billing_manager')

        self.reader_user = self.User.create({
            'name': 'مستخدم قارئ العداد',
            'login': 'reader_user_lifecycle_test',
            'email': 'reader_lifecycle@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_meter_reader').id])],
        })
        self.Staff.create({
            'name': 'قارئ ميداني',
            'employee_code': 'RDR-001',
            'user_id': self.reader_user.id,
            'role_ids': [(4, self.role_reader.id)],
            'region_id': self.region.id,
            'area_id': self.area.id,
        })

        self.supervisor_user = self.User.create({
            'name': 'مستخدم مشرف القراءات',
            'login': 'supervisor_user_lifecycle_test',
            'email': 'supervisor_lifecycle@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_supervisor').id])],
        })
        self.Staff.create({
            'name': 'مشرف قراءات',
            'employee_code': 'SUP-001',
            'user_id': self.supervisor_user.id,
            'role_ids': [(4, self.role_supervisor.id)],
            'region_id': self.region.id,
            'area_id': self.area.id,
        })

        self.billing_mgr_user = self.User.create({
            'name': 'مدير الفوترة التجريبي',
            'login': 'billing_mgr_lifecycle_test',
            'email': 'billing_mgr_lifecycle@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_billing_manager').id])],
        })
        self.Staff.create({
            'name': 'مدير فوترة',
            'employee_code': 'BM-001',
            'user_id': self.billing_mgr_user.id,
            'role_ids': [(4, self.role_billing_mgr.id)],
            'region_id': self.region.id,
            'area_id': self.area.id,
        })

    def _create_opening_reading(self, val=100.0):
        return self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': val,
            'reading_date': fields.Datetime.now() - timedelta(days=35),
            'reading_purpose': 'opening',
            'is_initial_reading': True,
            'image_state': 'clear',
            'meter_image': b'fake_image_data',
        })

    def test_01_meter_reader_cannot_approve(self):
        """Meter reader role must NOT have authorization to approve readings."""
        self._create_opening_reading(100.0)
        reading = self.Reading.with_user(self.reader_user).create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 250.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': b'fake_image_data',
        })
        reading.action_submit_review()
        self.assertEqual(reading.state, 'under_review')

        # Reader attempts to approve
        with self.assertRaises(AccessError):
            reading.with_user(self.reader_user).action_approve()

        # Reader attempts to reject
        with self.assertRaises(AccessError):
            reading.with_user(self.reader_user).action_reject()

    def test_02_supervisor_approve_and_queue(self):
        """Supervisor approves reading; billable reading immediately transitions to queued."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 300.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': b'fake_image_data',
        })
        reading.action_submit_review()

        # Supervisor approves
        reading.with_user(self.supervisor_user).action_approve()
        self.assertEqual(reading.state, 'queued')
        self.assertTrue(reading.is_validated)
        self.assertEqual(reading.validator_id.id, self.supervisor_user.id)
        self.assertEqual(reading.consumption, 200.0)

    def test_03_rejection_resets_to_draft_and_clears_validation(self):
        """Rejecting a reading moves it back to draft and clears validation flags."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 300.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': b'fake_image_data',
        })
        reading.action_submit_review()
        reading.write({'rejection_reason': 'الصورة غير واضحة ويوجد خطأ في الخانات'})

        reading.with_user(self.supervisor_user).action_reject()
        self.assertEqual(reading.state, 'draft')
        self.assertFalse(reading.is_validated)
        self.assertFalse(reading.validator_id)
        self.assertEqual(reading.rejection_reason, 'الصورة غير واضحة ويوجد خطأ في الخانات')

    def test_04_negative_consumption_blocked_on_approval(self):
        """Readings with negative consumption cannot be approved."""
        self._create_opening_reading(500.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 400.0,  # Negative consumption (400 - 500 = -100)
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': b'fake_image_data',
        })
        reading.action_submit_review()
        self.assertEqual(reading.consumption, -100.0)

        with self.assertRaises(ValidationError):
            reading.with_user(self.supervisor_user).action_approve()

    def test_05_meter_rollover_consumption(self):
        """Meter rollover (e.g. from 99800 to 50) correctly computes consumption when flagged."""
        self._create_opening_reading(99800.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 50.0,
            'is_rollover': True,
            'max_reading_value': 99999.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': b'fake_image_data',
        })
        # (99999 - 99800 + 1) + 50 = 200 + 50 = 250
        self.assertEqual(reading.raw_consumption, 250.0)
        self.assertEqual(reading.consumption, 250.0)

        reading.action_submit_review()
        reading.with_user(self.supervisor_user).action_approve()
        self.assertEqual(reading.state, 'queued')

    def test_06_duplicate_periodic_reading_in_same_period_blocked(self):
        """Cannot create two periodic readings for the same account in the same period."""
        self._create_opening_reading(100.0)
        self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 200.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': b'fake_image_data',
        })

        with self.assertRaises(ValidationError):
            self.Reading.create({
                'meter_id': self.meter.id,
                'account_id': self.customer.id,
                'reading_value': 250.0,
                'reading_date': fields.Datetime.now(),
                'reading_purpose': 'periodic',
                'date_range_id': self.date_range.id,
                'image_state': 'clear',
                'meter_image': b'fake_image_data',
            })

    def test_07_billing_authorization_and_immutability(self):
        """Only billing manager can generate bills; billed reading becomes immutable."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 300.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': b'fake_image_data',
        })
        reading.action_submit_review()
        reading.with_user(self.supervisor_user).action_approve()

        # Reader or Supervisor cannot generate bill
        with self.assertRaises(AccessError):
            reading.with_user(self.reader_user).action_generate_bill()
        with self.assertRaises(AccessError):
            reading.with_user(self.supervisor_user).action_generate_bill()

        # Billing manager generates bill
        reading.with_user(self.billing_mgr_user).action_generate_bill()
        self.assertEqual(reading.state, 'billed')
        self.assertTrue(reading.included_sale_order_id)

        # Billed reading cannot be rejected
        with self.assertRaises(ValidationError):
            reading.with_user(self.supervisor_user).action_reject()

        # Billed reading cannot have its reading value mutated
        with self.assertRaises(ValidationError):
            reading.write({'reading_value': 400.0})
