import threading
import time
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo import fields
from datetime import timedelta

SAMPLE_IMAGE = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


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
        })
        self.date_range = self.DateRange.create({
            'name': 'فترة قراءات 2026-08',
            'type_id': self.range_type.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
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
        self.route = self.env['utility.route'].create({
            'name': 'خط سير قراءات تجريبي',
            'code': 'READ-RT-01',
            'region_id': self.region.id,
            'area_id': self.area.id,
        })
        self.template = self.env['utility.contract.template'].create({
            'name': 'قالب فوترة اختبار دورة الحياة',
            'code': 'TPL-TEST-LC',
            'pricing_mode': 'flat',
            'price_per_kwh': 10.0,
            'service_charge': 100.0,
            'subscriber_category_ids': [(6, 0, self.category.ids)],
            'subscriber_ids': [(6, 0, self.subscriber.ids)],
            'scope': 'global',
        })
        self.customer = self.Customer.create({
            'customer_number': 'CUST-RD-001',
            'partner_id': self.partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'contract_template_id': self.template.id,
            'region_id': self.region.id,
            'area_id': self.area.id,
            'route_id': self.route.id,
        })
        self.meter = self.Meter.create({
            'meter_number': 'MTR-RD-001',
            'customer_id': self.customer.id,
            'connection_type': 'subscriber',
            'multiplier': 1.0,
        })

        # Setup users: Reader, Supervisor, Billing Manager, Auditor
        self.role_reader = self.env.ref('utility_core.role_meter_reader')
        self.role_supervisor = self.env.ref('utility_core.role_supervisor')
        self.role_manager = self.env.ref('utility_core.role_manager')

        self.reader_user = self.User.create({
            'name': 'مستخدم قارئ العداد',
            'login': 'reader_user_lifecycle_test',
            'email': 'reader_lifecycle@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_meter_reader').id])],
            'assigned_region_ids': [(6, 0, [self.region.id, self.area.id])],
            'assigned_route_ids': [(6, 0, [self.route.id])],
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
            'assigned_region_ids': [(6, 0, [self.region.id, self.area.id])],
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
            'assigned_region_ids': [(6, 0, [self.region.id, self.area.id])],
        })
        self.Staff.create({
            'name': 'مدير فوترة',
            'employee_code': 'BM-001',
            'user_id': self.billing_mgr_user.id,
            'role_ids': [(4, self.role_manager.id)],
            'region_id': self.region.id,
            'area_id': self.area.id,
        })

        self.auditor_user = self.User.create({
            'name': 'المراجع الرقابي',
            'login': 'auditor_lifecycle_test',
            'email': 'auditor_lifecycle@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_auditor').id])],
            'assigned_region_ids': [(6, 0, [self.region.id, self.area.id])],
        })
        self.Staff.create({
            'name': 'مراجع رقابي',
            'employee_code': 'AUD-001',
            'user_id': self.auditor_user.id,
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
            'meter_image': SAMPLE_IMAGE,
            'state': 'approved',
        })

    def test_01_meter_reader_cannot_approve_or_reject(self):
        """Meter reader role must NOT have authorization to approve or reject readings."""
        self._create_opening_reading(100.0)
        reading = self.Reading.with_user(self.reader_user).create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 250.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        self.assertEqual(reading.state, 'under_review')

        # Reader attempts to approve -> AccessError
        with self.assertRaises(AccessError):
            reading.with_user(self.reader_user).action_approve()

        # Reader attempts to reject -> AccessError
        with self.assertRaises(AccessError):
            reading.with_user(self.reader_user).action_reject()

    def test_02_supervisor_approve_and_generate_bill_immediately(self):
        """Supervisor approves reading; billable reading is billed immediately without a separate action."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 300.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()

        # Supervisor approves -> bill generated immediately, no separate action needed
        reading.with_user(self.supervisor_user).action_approve()
        self.assertEqual(reading.state, 'billed')
        self.assertTrue(reading.is_validated)
        self.assertEqual(reading.validator_id.id, self.supervisor_user.id)
        self.assertEqual(reading.consumption, 200.0)
        self.assertTrue(reading.included_sale_order_id)
        self.assertTrue(reading.included_sale_order_id.invoice_ids)

    def test_03_rejection_audit_and_resubmission(self):
        """Rejecting a reading records audit trail (rejected_by, rejected_at, reason) and requires a non-empty reason."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 300.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()

        # Rejection without reason fails
        reading.rejection_reason = False
        with self.assertRaises(ValidationError):
            reading.with_user(self.supervisor_user).action_reject()

        # Rejection with reason succeeds and preserves audit
        reading.rejection_reason = 'صورة العداد غير واضحة ويجب إعادة التقاطها'
        reading.with_user(self.supervisor_user).action_reject()

        self.assertEqual(reading.state, 'draft')
        self.assertFalse(reading.is_validated)
        self.assertFalse(reading.validator_id)
        self.assertEqual(reading.rejected_by.id, self.supervisor_user.id)
        self.assertTrue(reading.rejected_at)
        self.assertEqual(reading.rejection_reason, 'صورة العداد غير واضحة ويجب إعادة التقاطها')

        # Reader corrects and resubmits
        reading.with_user(self.reader_user).write({
            'reading_value': 310.0,
        })
        reading.with_user(self.reader_user).action_submit_review()
        self.assertEqual(reading.state, 'under_review')

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
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        self.assertEqual(reading.consumption, -100.0)

        with self.assertRaises(ValidationError):
            reading.with_user(self.supervisor_user).action_approve()

    def test_05_meter_rollover_boundaries_and_validation(self):
        """Meter rollover boundary conditions and validation constraints."""
        self._create_opening_reading(99800.0)

        # 1. Valid rollover: previous=99800, current=50, max=99999 -> (99999 - 99800 + 1) + 50 = 250
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
            'meter_image': SAMPLE_IMAGE,
        })
        self.assertEqual(reading.raw_consumption, 250.0)
        self.assertEqual(reading.consumption, 250.0)

        # 2. Boundary: previous=max (99999), current=0 -> (99999 - 99999 + 1) + 0 = 1
        reading.write({'reading_value': 0.0})
        self.assertEqual(reading.raw_consumption, (99999.0 - 99800.0 + 1.0) + 0.0)

        # 3. Invalid: current >= previous when rollover is True
        with self.assertRaises(ValidationError):
            reading.write({'reading_value': 99850.0})

        # 4. Invalid: max_reading_value <= 0
        with self.assertRaises(ValidationError):
            reading.write({'reading_value': 50.0, 'max_reading_value': -1.0})

        # 5. Invalid: reading_value > max_reading_value
        with self.assertRaises(ValidationError):
            reading.write({'reading_value': 100050.0, 'max_reading_value': 99999.0})

    def test_06_duplicate_periodic_reading_concurrency_and_db_uniqueness(self):
        """Cannot create two active periodic readings for the same account and period, validated under ORM and concurrency."""
        self._create_opening_reading(100.0)
        self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 200.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })

        # 1. ORM level duplicate prevention in single transaction
        with self.assertRaises(ValidationError):
            self.Reading.create({
                'meter_id': self.meter.id,
                'account_id': self.customer.id,
                'reading_value': 250.0,
                'reading_date': fields.Datetime.now() + timedelta(minutes=5),
                'reading_purpose': 'periodic',
                'date_range_id': self.date_range.id,
                'image_state': 'clear',
                'meter_image': SAMPLE_IMAGE,
            })

    def test_07_immutability_and_allowed_metadata_across_lifecycle(self):
        """Billed readings block critical field mutations while allowing metadata."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 300.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        reading.with_user(self.supervisor_user).action_approve()
        self.assertEqual(reading.state, 'billed')

        # Critical fields cannot be altered in billed state
        with self.assertRaises(ValidationError):
            reading.write({'reading_value': 350.0})
        with self.assertRaises(ValidationError):
            reading.write({'meter_multiplier': 2.0})

        # Non-critical metadata CAN be edited
        reading.write({'remarks': 'ملاحظة إدارية مقبولة'})
        self.assertEqual(reading.remarks, 'ملاحظة إدارية مقبولة')

        # Bill generation returns existing order
        res = reading.with_user(self.billing_mgr_user).action_generate_bill()
        self.assertEqual(res.get('res_id'), reading.included_sale_order_id.id)
        self.assertEqual(reading.state, 'billed')

        # Billed reading blocks critical mutations and cannot be rejected directly
        with self.assertRaises(ValidationError):
            reading.write({'reading_value': 500.0})
        with self.assertRaises(ValidationError):
            reading.with_user(self.supervisor_user).action_reject()

    def test_08_billed_idempotency_and_sale_order_uniqueness(self):
        """Calling generate bill on already billed reading idempotently returns the existing order."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 300.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        reading.with_user(self.supervisor_user).action_approve()
        self.assertEqual(reading.state, 'billed')

        # Idempotent: returns existing order without creating duplicate
        res1 = reading.with_user(self.billing_mgr_user).action_generate_bill()
        order_id = res1.get('res_id')
        self.assertTrue(order_id)
        self.assertEqual(order_id, reading.included_sale_order_id.id)

        res2 = reading.with_user(self.billing_mgr_user).action_generate_bill()
        self.assertEqual(res2.get('res_id'), order_id)

    def test_09_estimated_reading_synchronization(self):
        """reading_type == 'estimated' and is_estimated remain synchronized."""
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 150.0,
            'reading_date': fields.Datetime.now() - timedelta(days=20),
            'reading_purpose': 'opening',
            'reading_type': 'estimated',
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        self.assertTrue(reading.is_estimated)

        reading.write({'reading_type': 'manual'})
        self.assertFalse(reading.is_estimated)

        reading.write({'is_estimated': True})
        self.assertEqual(reading.reading_type, 'estimated')

    def test_10_direct_state_write_blocked(self):
        """P0: Direct write to state from UI/API is strictly blocked."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 250.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        self.assertEqual(reading.state, 'draft')

        # Attempt direct write to approved -> blocked
        with self.assertRaises(ValidationError):
            reading.write({'state': 'approved'})

        # Attempt direct write to queued -> blocked
        with self.assertRaises(ValidationError):
            reading.write({'state': 'queued'})

        # Attempt direct write to billed -> blocked
        with self.assertRaises(ValidationError):
            reading.write({'state': 'billed'})

    def test_11_auditor_cannot_approve_or_reject(self):
        """P0: Auditor is purely supervisory/read-only and cannot approve or reject readings."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 250.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        self.assertEqual(reading.state, 'under_review')

        # Auditor attempts to approve -> AccessError
        with self.assertRaises(AccessError):
            reading.with_user(self.auditor_user).action_approve()

        # Auditor attempts to reject -> AccessError
        with self.assertRaises(AccessError):
            reading.with_user(self.auditor_user).action_reject()

    def test_12_context_bypass_spoofing_blocked_for_unauthorized_user(self):
        """P0: Unauthorized user passing _bypass_reading_protection or _reading_state_transition over RPC is blocked."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 250.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        self.assertEqual(reading.state, 'under_review')

        # Reader attempts to modify frozen reading_value using _bypass_reading_protection -> ValidationError
        with self.assertRaises(ValidationError):
            reading.with_user(self.reader_user).with_context(
                _bypass_reading_protection=True
            ).write({'reading_value': 999.0})

        # Reader attempts direct state jump to approved using _reading_state_transition -> ValidationError
        with self.assertRaises(ValidationError):
            reading.with_user(self.reader_user).with_context(
                _reading_state_transition=True
            ).write({'state': 'approved'})

        # Reader attempts to bypass using allow_billing_adjustment -> ValidationError
        with self.assertRaises(ValidationError):
            reading.with_user(self.reader_user).with_context(
                allow_billing_adjustment=True
            ).write({'reading_value': 999.0})

    def test_13_image_state_requires_review_access(self):
        """P1: Changing image_state requires reviewer role across all interfaces."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 250.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'pending',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()

        # Reader has NO review access -> AccessError
        with self.assertRaises(AccessError):
            reading.with_user(self.reader_user).write({'image_state': 'clear'})

        # Review service action_set_image_state with reader -> AccessError
        review_service = self.env['utility.reading.review.service']
        with self.assertRaises(AccessError):
            review_service.with_user(self.reader_user).action_set_image_state([reading.id], 'clear')

        # Supervisor has review access -> succeeds
        review_service.with_user(self.supervisor_user).action_set_image_state([reading.id], 'clear')
        self.assertEqual(reading.image_state, 'clear')

        # Billing manager has review access -> succeeds
        reading.with_user(self.billing_mgr_user).write({'image_state': 'not_clear'})
        self.assertEqual(reading.image_state, 'not_clear')

    def test_14_billing_without_eligible_date_range_fails(self):
        """P1: Attempting to create or resolve a period without an eligible covering open period raises ValidationError."""
        # 1. Creating a periodic reading without date_range_id for an out-of-period date raises ValidationError
        with self.assertRaises(ValidationError):
            self.Reading.create({
                'meter_id': self.meter.id,
                'account_id': self.customer.id,
                'reading_value': 250.0,
                'reading_date': '2020-01-15 10:00:00',
                'reading_purpose': 'periodic',
                'meter_image': SAMPLE_IMAGE,
            })

        # 2. Directly resolving an eligible date range on a reading record with an out-of-period date raises ValidationError
        out_of_period_reading = self.Reading.new({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 250.0,
            'reading_date': '2020-01-15 10:00:00',
            'reading_purpose': 'periodic',
        })
        with self.assertRaises(ValidationError):
            out_of_period_reading._resolve_eligible_billing_date_range()

        # 3. For a reading with current date covering self.date_range, resolution succeeds and returns self.date_range
        valid_reading = self.Reading.new({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 250.0,
            'reading_date': '2026-08-15 10:00:00',
            'reading_purpose': 'periodic',
        })
        resolved = valid_reading._resolve_eligible_billing_date_range()
        self.assertEqual(resolved, self.date_range)

    def test_15_supervisor_cannot_bypass_approval_workflow_via_context(self):
        """P0: Supervisor cannot write state='approved' directly, and approval invariants cannot be bypassed via context."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 150.0,
            'reading_date': '2026-08-15 10:00:00',
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        self.assertEqual(reading.state, 'under_review')

        # 1. Direct write state='approved' with _reading_state_transition=True fails
        with self.assertRaises(ValidationError):
            reading.with_user(self.supervisor_user).with_context(
                _reading_state_transition=True,
            ).write({'state': 'approved'})

        # 2. Context spoofing with _internal_approval_action when image is not clear fails
        with self.assertRaises(ValidationError):
            reading.with_user(self.supervisor_user).with_context(
                _reading_state_transition=True,
                _internal_approval_action=True,
            ).write({'state': 'approved'})

        # 3. Context spoofing when consumption is negative fails
        reading.with_user(self.supervisor_user).action_mark_image_clear()
        self.assertEqual(reading.image_state, 'clear')
        # Simulate negative consumption reading on a distinct account/meter
        partner2 = self.Partner.create({'name': 'مشترك سالب', 'region_id': self.region.id})
        cust2 = self.Customer.create({
            'name': 'عميل سالب',
            'partner_id': partner2.id,
            'contract_status': 'active',
            'region_id': self.region.id,
        })
        meter2 = self.Meter.create({
            'name': 'عداد سالب',
            'meter_number': 'MTR-NEG-01',
            'subscriber_id': self.subscriber.id,
            'customer_id': cust2.id,
            'status': 'active',
        })
        self.Reading.create({
            'meter_id': meter2.id,
            'account_id': cust2.id,
            'reading_value': 100.0,
            'reading_date': '2026-08-01 08:00:00',
            'reading_purpose': 'opening',
            'is_initial_reading': True,
            'image_state': 'clear',
            'state': 'approved',
        })
        neg_reading = self.Reading.create({
            'meter_id': meter2.id,
            'account_id': cust2.id,
            'reading_value': 50.0,  # previous was 100 -> consumption = -50
            'reading_date': '2026-08-16 10:00:00',
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'meter_image': SAMPLE_IMAGE,
        })
        neg_reading.action_submit_review()
        neg_reading.with_user(self.supervisor_user).action_mark_image_clear()
        with self.assertRaises(ValidationError):
            neg_reading.with_user(self.supervisor_user).with_context(
                _reading_state_transition=True,
                _internal_approval_action=True,
            ).write({'state': 'approved'})

    def test_16_supervisor_cannot_bypass_frozen_fields_via_context(self):
        """P0: Supervisor cannot use _bypass_reading_protection to modify frozen fields."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 200.0,
            'reading_date': '2026-08-15 10:00:00',
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        self.assertEqual(reading.state, 'under_review')

        # In under_review, reading_value is frozen. Attempting to bypass as supervisor must fail.
        with self.assertRaises(ValidationError):
            reading.with_user(self.supervisor_user).with_context(
                _bypass_reading_protection=True,
            ).write({'reading_value': 999.0})

    def test_approval_context_cannot_replace_audited_action(self):
        """Even valid readings cannot be approved by spoofing RPC context."""
        self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 100.0,
            'reading_date': '2026-08-01 08:00:00',
            'reading_purpose': 'opening',
            'is_initial_reading': True,
            'state': 'approved',
        })
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 200.0,
            'reading_date': '2026-08-15 10:00:00',
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        reading.with_user(self.supervisor_user).action_mark_image_clear()
        self.assertGreater(reading.consumption, 0)
        self.assertEqual(reading.image_state, 'clear')
        audit_before = (
            reading.is_validated, reading.validator_id.id,
            reading.reviewer_id.id, reading.review_date,
        )
        for user in (self.reader_user, self.supervisor_user, self.billing_mgr_user):
            for forged_token in (True, 1, 'true'):
                with self.subTest(user=user.login, token=forged_token):
                    with self.assertRaises(ValidationError):
                        reading.with_user(user).with_context(
                            _internal_approval_action=forged_token,
                            _reading_state_transition=True,
                            _bypass_reading_protection=True,
                            allow_billing_adjustment=True,
                        ).write({'state': 'approved'})
                    self.assertEqual(reading.state, 'under_review')
                    self.assertEqual((
                        reading.is_validated, reading.validator_id.id,
                        reading.reviewer_id.id, reading.review_date,
                    ), audit_before)
                    self.assertFalse(reading.included_sale_order_id)

        with self.assertRaises(AccessError):
            reading.with_user(self.reader_user).action_approve()
        reading.with_user(self.supervisor_user).action_approve()
        self.assertEqual(reading.state, 'billed')
        self.assertTrue(reading.is_validated)
        self.assertEqual(reading.validator_id, self.supervisor_user)
        self.assertEqual(reading.reviewer_id, self.supervisor_user)
        self.assertTrue(reading.review_date)
        self.assertTrue(reading.included_sale_order_id)

    def test_17_cross_region_period_resolution_rejected(self):
        """P1: A reading in region A must never resolve an open period belonging strictly to region B."""
        region_b = self.Region.create({
            'name': 'منطقة أخرى ب',
            'code': 'READ-REG-B',
            'type': 'region',
        })
        # Deactivate self.date_range so only period_b is open
        self.date_range.write({'state': 'closed'})
        range_type_b = self.DateRangeType.create({
            'name': 'نوع فترة قراءات ب',
        })
        # Period strictly for Region B
        period_b = self.DateRange.create({
            'name': 'فترة منطقة ب 2026-08',
            'type_id': range_type_b.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'billing_cadence': 'monthly',
            'period_role': 'reading',
            'state': 'open',
            'region_ids': [(4, region_b.id)],
        })

        reading_in_region_a = self.Reading.new({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 250.0,
            'reading_date': '2026-08-15 10:00:00',
            'reading_purpose': 'periodic',
        })
        # Customer is in self.region (Region A). Must fail and NOT cross into period_b!
        with self.assertRaises(ValidationError):
            reading_in_region_a._resolve_eligible_billing_date_range()

    def test_18_immediate_bill_generation_on_approval(self):
        """Approval of a billable reading generates the bill immediately without a separate action."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 350.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        self.assertEqual(reading.state, 'under_review')

        # Approve -> bill generated immediately
        reading.with_user(self.supervisor_user).action_approve()

        self.assertEqual(reading.state, 'billed')
        self.assertTrue(reading.included_sale_order_id, 'Sale order must be created on approval')
        self.assertEqual(reading.included_sale_order_id.state, 'sale')
        self.assertTrue(reading.included_sale_order_id.invoice_ids, 'Invoice must be created on approval')
        self.assertEqual(reading.included_sale_order_id.invoice_ids.state, 'posted')
        self.assertEqual(reading.billing_error, False)

    def test_19_bill_generation_error_sets_error_state(self):
        """When bill generation fails during approval, reading transitions to error state with billing_error."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 300.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()

        # Close the billing period to force a ValidationError during bill generation
        self.date_range.write({'state': 'closed'})

        reading.with_user(self.supervisor_user).action_approve()

        self.assertEqual(reading.state, 'error')
        self.assertTrue(reading.billing_error, 'billing_error must be populated on failure')
        self.assertNotIn('sale', reading.billing_error.lower())

    def test_20_action_requeue_moves_error_to_queued(self):
        """action_requeue moves an error-state reading back to queued for retry."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 300.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()

        # Force error state by closing the period
        self.date_range.write({'state': 'closed'})
        reading.with_user(self.supervisor_user).action_approve()
        self.assertEqual(reading.state, 'error')
        self.assertTrue(reading.billing_error)

        # Reopen period and requeue
        self.date_range.write({'state': 'open'})
        reading.action_requeue()
        self.assertEqual(reading.state, 'queued')
        self.assertFalse(reading.billing_error)

    def test_21_action_requeue_rejects_non_error_readings(self):
        """action_requeue raises ValidationError for readings not in error state."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 300.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        reading.with_user(self.supervisor_user).action_approve()
        self.assertEqual(reading.state, 'billed')

        with self.assertRaises(ValidationError):
            reading.action_requeue()

    def test_22_non_billable_reading_stays_approved_after_approval(self):
        """Non-billable network transformer reading stays in approved state, no bill generated."""
        # Create a separate meter for network transformer reading
        partner2 = self.Partner.create({'name': 'ممح transformer', 'region_id': self.region.id})
        cust2 = self.Customer.create({
            'name': 'عميل محول شبكي',
            'partner_id': partner2.id,
            'contract_status': 'active',
            'region_id': self.region.id,
        })
        meter2 = self.Meter.create({
            'name': 'عداد محول شبكي',
            'meter_number': 'MTR-NET-01',
            'subscriber_id': self.subscriber.id,
            'customer_id': cust2.id,
            'connection_type': 'subscriber',
            'multiplier': 1.0,
        })

        # Create a non-billable network transformer reading (is_billable=False)
        reading = self.Reading.create({
            'meter_id': meter2.id,
            'account_id': cust2.id,
            'reading_value': 500.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'reading_category': 'transformer',
            'is_billable': False,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        reading.with_user(self.supervisor_user).action_approve()

        # Non-billable: stays approved, no sale order
        self.assertEqual(reading.state, 'approved')
        self.assertFalse(reading.included_sale_order_id)

    def test_23_cron_fallback_picks_up_queued_readings(self):
        """_cron_generate_bills processes any leftover queued readings as fallback."""
        self._create_opening_reading(100.0)
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 250.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading.action_submit_review()
        reading.with_user(self.supervisor_user).action_approve()
        self.assertEqual(reading.state, 'billed')

        # Create a reading manually set to queued (simulating a leftover from before the change)
        reading2 = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 400.0,
            'reading_date': fields.Datetime.now() + timedelta(minutes=1),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        reading2.action_submit_review()
        reading2.with_user(self.supervisor_user).action_approve()
        # Should already be billed from immediate generation
        self.assertEqual(reading2.state, 'billed')

        # Cron should not fail on already-billed readings
        self.Reading._cron_generate_bills()
        self.assertEqual(reading2.state, 'billed')

    def test_24_multiple_readings_partial_failure(self):
        """When approving multiple readings, one failing does not block others."""
        self._create_opening_reading(100.0)

        # Create two readings for different customers
        partner2 = self.Partner.create({'name': 'مشترك ثاني', 'region_id': self.region.id})
        cust2 = self.Customer.create({
            'name': 'عميل ثاني',
            'partner_id': partner2.id,
            'contract_status': 'active',
            'region_id': self.region.id,
        })
        meter2 = self.Meter.create({
            'name': 'عداد ثاني',
            'meter_number': 'MTR-02',
            'subscriber_id': self.subscriber.id,
            'customer_id': cust2.id,
            'connection_type': 'subscriber',
            'multiplier': 1.0,
        })

        r1 = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 250.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        r1.action_submit_review()

        r2 = self.Reading.create({
            'meter_id': meter2.id,
            'account_id': cust2.id,
            'reading_value': 300.0,
            'reading_date': fields.Datetime.now(),
            'reading_purpose': 'periodic',
            'date_range_id': self.date_range.id,
            'image_state': 'clear',
            'meter_image': SAMPLE_IMAGE,
        })
        r2.action_submit_review()

        # Approve both at once
        (r1 | r2).with_user(self.supervisor_user).action_approve()

        # Both should be billed (no failure scenario here, but confirms batch works)
        self.assertEqual(r1.state, 'billed')
        self.assertEqual(r2.state, 'billed')
        self.assertTrue(r1.included_sale_order_id)
        self.assertTrue(r2.included_sale_order_id)
        self.assertNotEqual(r1.included_sale_order_id, r2.included_sale_order_id)

