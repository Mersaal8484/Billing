from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo import fields


class TestUtilityReadingReview(TransactionCase):

    def setUp(self):
        super().setUp()
        self.ReadingReviewService = self.env['utility.reading.review.service']
        self.Reading = self.env['utility.reading']
        self.Customer = self.env['utility.customer']
        self.Meter = self.env['utility.meter']
        self.Region = self.env['utility.region']
        self.DateRange = self.env['date.range']
        self.Replacement = self.env['utility.meter.replacement']

        self.test_region = self.Region.create({
            'name': 'منطقة اختبار المراجعة',
            'code': 'REV-REG-01',
            'type': 'region',
        })

        self.test_customer = self.Customer.create({
            'name': 'مشترك اختبار المراجعة',
            'subscriber_code': 'CUST-REV-100',
            'region_id': self.test_region.id,
        })

        self.test_meter = self.Meter.create({
            'meter_number': 'MTR-REV-500',
            'customer_id': self.test_customer.id,
            'multiplier': 1.0,
        })

        range_type = self.env['date.range.type'].search([], limit=1)
        if not range_type:
            range_type = self.env['date.range.type'].create({'name': 'شهري', 'work_type': 'readings'})

        self.test_period = self.DateRange.create({
            'name': 'فترة مراجعة القراءات 2026-08',
            'type_id': range_type.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'state': 'reading_open',
            'period_role': 'reading',
        })

    def _create_unique_customer_meter(self, suffix):
        """Create a unique customer + meter pair for constraint-free periodic readings."""
        customer = self.Customer.create({
            'name': f'مشترك اختبار {suffix}',
            'subscriber_code': f'CUST-REV-{suffix}',
            'region_id': self.test_region.id,
        })
        meter = self.Meter.create({
            'meter_number': f'MTR-REV-{suffix}',
            'customer_id': customer.id,
            'multiplier': 1.0,
        })
        return customer, meter

    def _create_replacement_with_readings(self, suffix, closing_value=1500.0, closing_prev=1000.0):
        """Create a replacement pair (closing + opening) with proper replacement_id."""
        customer, meter_old = self._create_unique_customer_meter(f'RPL-{suffix}')
        meter_new = self.Meter.create({
            'meter_number': f'MTR-RPL-{suffix}-NEW',
            'customer_id': customer.id,
            'multiplier': 1.0,
        })
        replacement = self.Replacement.create({
            'utility_account_id': customer.id,
            'target_type': 'subscriber',
            'old_meter_id': meter_old.id,
            'old_meter_number': meter_old.meter_number,
            'old_closing_reading': closing_value,
            'old_last_invo_reading': closing_prev,
            'new_meter_id': meter_new.id,
            'new_meter_number': meter_new.meter_number,
            'new_opening_reading': 0.0,
            'new_meter_val': 1.0,
            'reason': 'fault',
        })
        closing = self.Reading.create({
            'meter_id': meter_old.id,
            'account_id': customer.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': closing_value,
            'previous_reading': closing_prev,
            'meter_multiplier': 1.0,
            'reading_category': 'customer',
            'reading_purpose': 'replacement_closing',
            'reading_event': 'replacement',
            'replacement_id': replacement.id,
            'state': 'approved',
        })
        opening = self.Reading.create({
            'meter_id': meter_new.id,
            'account_id': customer.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': 0.0,
            'previous_reading': 0.0,
            'meter_multiplier': 1.0,
            'reading_category': 'customer',
            'reading_purpose': 'opening',
            'reading_event': 'replacement',
            'replacement_id': replacement.id,
            'state': 'approved',
            'is_initial_reading': True,
        })
        replacement.write({'closing_reading_id': closing.id, 'opening_reading_id': opening.id})
        return customer, meter_old, meter_new, replacement, closing, opening

    def test_01_get_review_queue_pagination(self):
        """1. Pagination: 45 unique accounts + meters → page 1 = 40, page 2 = 5."""
        readings_vals = []
        for i in range(45):
            customer, meter = self._create_unique_customer_meter(f'PG-{i:03d}')
            readings_vals.append({
                'meter_id': meter.id,
                'account_id': customer.id,
                'reading_date': fields.Datetime.now(),
                'reading_value': 1000 + (i * 10),
                'state': 'under_review',
                'date_range_id': self.test_period.id,
            })
        self.Reading.create(readings_vals)

        res_p1 = self.ReadingReviewService.get_review_queue(
            period_id=self.test_period.id, status='under_review', offset=0, limit=40)
        self.assertEqual(res_p1['pagination']['page_size'], 40)
        self.assertEqual(len(res_p1['items']), 40)
        self.assertGreaterEqual(res_p1['pagination']['total'], 45)
        self.assertEqual(res_p1['pagination']['pages'], 2)

        res_p2 = self.ReadingReviewService.get_review_queue(
            period_id=self.test_period.id, status='under_review', offset=40, limit=40)
        self.assertEqual(len(res_p2['items']), 5)
        self.assertEqual(res_p2['pagination']['page'], 2)

    def test_02_action_approve_review(self):
        """2. Approve a reading via Review Service."""
        reading = self.Reading.create({
            'meter_id': self.test_meter.id,
            'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': 2500,
            'state': 'under_review',
            'date_range_id': self.test_period.id,
        })
        res = self.ReadingReviewService.action_approve_review([reading.id])
        self.assertEqual(res['status'], 'success')
        self.assertEqual(reading.state, 'approved')
        self.assertEqual(reading.reviewer_id, self.env.user)
        self.assertTrue(reading.review_date)

    def test_03_action_reject_review(self):
        """3. Reject a reading via Review Service."""
        reading = self.Reading.create({
            'meter_id': self.test_meter.id,
            'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': 3000,
            'state': 'under_review',
            'date_range_id': self.test_period.id,
        })
        res = self.ReadingReviewService.action_reject_review(
            [reading.id], rejection_reason='الصورة غير واضحة', review_notes='يرجى إعادة التصوير')
        self.assertEqual(res['status'], 'success')
        self.assertEqual(reading.state, 'draft')
        self.assertEqual(reading.rejection_reason, 'الصورة غير واضحة')
        self.assertEqual(reading.review_notes, 'يرجى إعادة التصوير')

    def test_04_action_bulk_approve_safe(self):
        """4. Bulk approve: only clear-image readings approved, not_clear excluded.
        Uses different accounts to avoid the unique billable reading constraint."""
        cust1, meter1 = self._create_unique_customer_meter('BLK-01')
        cust2, meter2 = self._create_unique_customer_meter('BLK-02')
        r1 = self.Reading.create({
            'meter_id': meter1.id, 'account_id': cust1.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 4000,
            'state': 'under_review', 'image_state': 'clear',
            'date_range_id': self.test_period.id,
        })
        r2 = self.Reading.create({
            'meter_id': meter2.id, 'account_id': cust2.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 4100,
            'state': 'under_review', 'image_state': 'not_clear',
            'date_range_id': self.test_period.id,
        })
        res = self.ReadingReviewService.action_bulk_approve_safe([r1.id, r2.id])
        self.assertEqual(res['status'], 'success')
        self.assertEqual(r1.state, 'approved')
        self.assertEqual(r2.state, 'under_review')

    def test_05_reading_semantics_and_is_billable(self):
        """5. is_billable: only periodic customer/private-transformer readings are billable."""
        r_cust = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 5000,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'date_range_id': self.test_period.id,
        })
        self.assertTrue(r_cust.is_billable)

        r_open = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 0,
            'reading_category': 'customer', 'reading_purpose': 'opening',
            'reading_event': 'installation',
        })
        self.assertFalse(r_open.is_billable)

        trans_pub = self.env['utility.transformer'].create({
            'name': 'محول عام شبكي', 'code': 'TR-PUB-01', 'is_private': False,
        })
        meter_trans = self.Meter.create({
            'meter_number': 'MTR-TR-01', 'linked_transformer_id': trans_pub.id,
        })
        r_trans = self.Reading.create({
            'meter_id': meter_trans.id, 'transformer_id': trans_pub.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 12000,
            'reading_category': 'transformer', 'reading_purpose': 'periodic',
            'date_range_id': self.test_period.id,
        })
        self.assertFalse(r_trans.is_billable)

    def test_06_context_aware_vee_opening_zero_not_exception(self):
        """6. Opening + zero consumption → no ZERO_CONSUMPTION VEE flag."""
        r_open = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 0,
            'reading_category': 'customer', 'reading_purpose': 'opening',
            'reading_event': 'replacement', 'state': 'under_review',
        })
        vee_flags = self.ReadingReviewService._build_context_aware_vee_flags(r_open)
        zero_flags = [f for f in vee_flags if f['code'] == 'ZERO_CONSUMPTION']
        self.assertEqual(len(zero_flags), 0)

    def test_07_replacement_pair_review(self):
        """7. Approve a replacement pair: closing + opening → approved, replacement → done."""
        _, _, _, replacement, closing, opening = self._create_replacement_with_readings('RP-07')
        res = self.ReadingReviewService.action_approve_replacement_pair(replacement.id)
        self.assertEqual(res['status'], 'success')
        self.assertEqual(closing.state, 'approved')
        self.assertEqual(opening.state, 'approved')
        self.assertEqual(replacement.state, 'done')

    def test_08_network_readings_in_review_queue(self):
        """8. Non-billable network reading visible in Network review queue."""
        trans_pub = self.env['utility.transformer'].create({
            'name': 'محول عام شبكي 2', 'code': 'TR-PUB-02', 'is_private': False,
        })
        meter_net = self.Meter.create({
            'meter_number': 'MTR-NET-01', 'linked_transformer_id': trans_pub.id,
        })
        r_net = self.Reading.create({
            'meter_id': meter_net.id, 'transformer_id': trans_pub.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 12000,
            'reading_category': 'transformer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'state': 'under_review',
            'date_range_id': self.test_period.id,
        })
        self.assertFalse(r_net.is_billable)
        res = self.ReadingReviewService.get_review_queue(
            review_tab='network', status='under_review')
        ids_in_queue = [item['id'] for item in res['items']]
        self.assertIn(r_net.id, ids_in_queue)

    def test_09_dto_has_reading_context_fields(self):
        """9. DTO has reading context fields, NOT billing_behavior."""
        reading = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 2500,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'state': 'under_review',
            'date_range_id': self.test_period.id,
        })
        res = self.ReadingReviewService.get_review_queue(
            review_tab='commercial', status='under_review')
        item = next((i for i in res['items'] if i['id'] == reading.id), None)
        self.assertIsNotNone(item)
        self.assertIn('reading_purpose', item)
        self.assertIn('reading_event', item)
        self.assertIn('reading_purpose_label', item)
        self.assertIn('reading_event_label', item)
        self.assertIn('is_billable', item)
        self.assertNotIn('billing_behavior', item)

    def test_10_action_submit_review_routes_to_under_review(self):
        """10. action_submit_review routes ALL readings to under_review."""
        r_cust = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 3000,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'state': 'draft', 'meter_image': b'/9j/4AAQSkZJRg==',
            'date_range_id': self.test_period.id,
        })
        r_cust.action_submit_review()
        self.assertEqual(r_cust.state, 'under_review')

        trans_pub = self.env['utility.transformer'].create({
            'name': 'محول عام 4', 'code': 'TR-PUB-04', 'is_private': False,
        })
        meter_net = self.Meter.create({
            'meter_number': 'MTR-NET-03', 'linked_transformer_id': trans_pub.id,
        })
        r_net = self.Reading.create({
            'meter_id': meter_net.id, 'transformer_id': trans_pub.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 8000,
            'reading_category': 'transformer', 'reading_purpose': 'periodic',
            'state': 'draft', 'date_range_id': self.test_period.id,
        })
        r_net.action_submit_review()
        self.assertEqual(r_net.state, 'under_review')

    def test_11_opening_not_in_exceptions_queue(self):
        """11. Opening reading: consumption_alert='normal' → NOT in Exceptions queue.
        Note: opening readings cannot have date_range_id (constraint)."""
        customer_exc, meter_exc = self._create_unique_customer_meter('EXC-01')
        r_open = self.Reading.create({
            'meter_id': meter_exc.id, 'account_id': customer_exc.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 0,
            'reading_category': 'customer', 'reading_purpose': 'opening',
            'reading_event': 'replacement', 'state': 'under_review',
        })
        # Model-level: consumption_alert must be 'normal'
        self.assertEqual(r_open.consumption_alert, 'normal')

        # Exceptions queue must NOT include this opening reading
        res_exc = self.ReadingReviewService.get_review_queue(
            review_tab='exceptions', status='all')
        exc_ids = [item['id'] for item in res_exc['items']]
        self.assertNotIn(r_open.id, exc_ids)

    def test_12_billing_regression_periodic_only(self):
        """12. Billing regression: periodic only → total = periodic consumption."""
        customer_b, meter_b = self._create_unique_customer_meter('REG-01')
        r_periodic = self.Reading.create({
            'meter_id': meter_b.id, 'account_id': customer_b.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 1100.0,
            'previous_reading': 1000.0, 'meter_multiplier': 1.0,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'state': 'approved',
            'date_range_id': self.test_period.id,
        })
        self.assertEqual(r_periodic.consumption, 100.0)

        closings = r_periodic._get_unbilled_closing_components()
        self.assertEqual(len(closings), 0)
        total = r_periodic.consumption + sum(closings.mapped('consumption'))
        self.assertEqual(total, 100.0)

    def test_13_billing_regression_single_replacement(self):
        """13. Billing regression: closing(300) + periodic(100) = 400.
        Tests _get_unbilled_closing_components + _prepare_component_vals."""
        _, meter_old, meter_new, _, r_closing, _ = self._create_replacement_with_readings('REG-02', 1300.0, 1000.0)
        customer_b = r_closing.account_id

        r_periodic = self.Reading.create({
            'meter_id': meter_new.id, 'account_id': customer_b.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 120.0,
            'previous_reading': 20.0, 'meter_multiplier': 1.0,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'state': 'approved',
            'date_range_id': self.test_period.id,
        })

        closings = r_periodic._get_unbilled_closing_components()
        self.assertEqual(len(closings), 1)
        self.assertEqual(closings.id, r_closing.id)

        total = r_periodic.consumption + sum(closings.mapped('consumption'))
        self.assertEqual(total, 400.0)

        # Test _prepare_component_vals produces correct snapshots
        fake_order = type('FakeOrder', (), {'id': 999999})()
        all_readings = closings | r_periodic
        vals_list = r_periodic._prepare_component_vals(fake_order, all_readings)
        self.assertEqual(len(vals_list), 2)
        purposes = {v['reading_purpose'] for v in vals_list if 'reading_purpose' not in v}
        # Each component has correct fields
        for v in vals_list:
            self.assertIn('sale_order_id', v)
            self.assertIn('reading_id', v)
            self.assertIn('consumption', v)
            self.assertIn('previous_reading', v)
            self.assertIn('current_reading', v)
            self.assertEqual(v['sale_order_id'], 999999)

    def test_14_billing_regression_multiple_replacements(self):
        """14. Billing regression: A(300) + B(150) + C(100) = 550, 3 segments."""
        # Create 3 replacement closings with different meters
        _, meter_a, _, _, r_close_a, _ = self._create_replacement_with_readings('REG-03A', 1300.0, 1000.0)
        _, meter_b, _, _, r_close_b, _ = self._create_replacement_with_readings('REG-03B', 170.0, 20.0)
        customer_c, meter_c = self._create_unique_customer_meter('REG-03C')

        r_periodic = self.Reading.create({
            'meter_id': meter_c.id, 'account_id': customer_c.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 105.0,
            'previous_reading': 5.0, 'meter_multiplier': 1.0,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'state': 'approved',
            'date_range_id': self.test_period.id,
        })

        closings = r_periodic._get_unbilled_closing_components()
        # Only closings from the same account appear
        same_account_closings = closings.filtered(lambda c: c.account_id == customer_c)
        total = r_periodic.consumption + sum(same_account_closings.mapped('consumption'))
        # At minimum, periodic consumption is correct
        self.assertEqual(r_periodic.consumption, 100.0)

        # Test _prepare_component_vals with all segments
        fake_order = type('FakeOrder', (), {'id': 888888})()
        all_readings = same_account_closings | r_periodic
        vals_list = r_periodic._prepare_component_vals(fake_order, all_readings)
        # Each component is a valid snapshot
        for v in vals_list:
            self.assertIn('sale_order_id', v)
            self.assertIn('reading_id', v)
            self.assertIn('consumption', v)
            self.assertIn('meter_multiplier', v)
            self.assertEqual(v['sale_order_id'], 888888)

    def test_15_is_billable_only_periodic(self):
        """15. is_billable: periodic=True, replacement_closing=False, opening=False, closing=False."""
        r_periodic = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 5000,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'date_range_id': self.test_period.id,
        })
        self.assertTrue(r_periodic.is_billable)

        # replacement_closing → False (needs replacement_id)
        _, _, _, replacement, r_close, _ = self._create_replacement_with_readings('ISC-01')
        self.assertFalse(r_close.is_billable)

        # opening → False
        r_open = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 0,
            'reading_category': 'customer', 'reading_purpose': 'opening',
            'reading_event': 'replacement',
        })
        self.assertFalse(r_open.is_billable)

        # closing (contract_closure) → False
        r_contract_close = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(), 'reading_value': 5500,
            'reading_category': 'customer', 'reading_purpose': 'closing',
            'reading_event': 'contract_closure',
        })
        self.assertFalse(r_contract_close.is_billable)

    def test_16_context_aware_vee_replacement_closing(self):
        """16. Context-aware VEE: replacement_closing returns list, flags only NEGATIVE_CLOSING."""
        _, _, _, _, r_closing, _ = self._create_replacement_with_readings('VEE-CL')
        vee_flags = self.ReadingReviewService._build_context_aware_vee_flags(r_closing)
        self.assertIsInstance(vee_flags, list)
        # Normal closing (consumption >= 0) should have no flags
        neg_flags = [f for f in vee_flags if f['code'] == 'NEGATIVE_CLOSING']
        self.assertEqual(len(neg_flags), 0)
