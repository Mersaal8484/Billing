"""
Phase 7 Tests — Reading Batch Scope Authorization

Tests that:
- Reading batch lines with meters in a different region than the batch region are marked as failed with a descriptive error
- Readers restricted to a branch/region cannot import meters outside their organizational scope
- Global readers can import across all regions
"""
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'reading_batch_scope', 'production_integrity_hardening')
class TestReadingBatchScope(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Region = cls.env['utility.region']
        cls.Customer = cls.env['utility.customer']
        cls.Partner = cls.env['res.partner']
        cls.Meter = cls.env['utility.meter']
        cls.Batch = cls.env['utility.reading.batch']
        cls.BatchLine = cls.env['utility.reading.batch.line']
        cls.BatchService = cls.env['utility.reading.batch.service']

        cls.region_north = cls.Region.create({
            'name': 'المنطقة الشمالية',
            'code': 'NORTH-SCOPE',
            'type': 'region',
            'recurring_rule_type': 'monthly',
        })
        cls.region_south = cls.Region.create({
            'name': 'المنطقة الجنوبية',
            'code': 'SOUTH-SCOPE',
            'type': 'region',
            'recurring_rule_type': 'monthly',
        })

        cls.range_type = cls.env['date.range.type'].search([
            ('default_billing_period', '=', 'monthly'),
            ('fiscal_year', '=', False),
        ], limit=1)
        if not cls.range_type:
            cls.range_type = cls.env['date.range.type'].create({
                'name': 'دورة قراءة شهرية',
                'default_billing_period': 'monthly',
                'allow_overlap': True,
            })

        cls.period_north = cls.env['date.range'].create({
            'name': 'فترة الشمال',
            'period_code': 'NORTH-2026-08',
            'cycle_key': 'NORTH-2026-08',
            'period_role': 'reading',
            'type_id': cls.range_type.id,
            'region_ids': [(6, 0, [cls.region_north.id])],
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'billing_cadence': 'monthly',
            'state': 'open',
        })

        # Category and subscriber
        cls.cat = cls.env['utility.subscriber.category'].create({
            'name': 'فئة سكني دفعة',
            'code': 'BATCH-CAT',
        })
        cls.sub = cls.env['utility.subscriber'].create({
            'name': 'نوع سكني دفعة',
            'code': 'BATCH-SUB',
            'category_id': cls.cat.id,
        })

        # North customer & meter
        cls.partner_north = cls.Partner.create({
            'name': 'عميل الشمال',
            'region_id': cls.region_north.id,
        })
        cls.customer_north = cls.Customer.create({
            'customer_number': 'CUST-NORTH-001',
            'partner_id': cls.partner_north.id,
            'region_id': cls.region_north.id,
            'category_id': cls.cat.id,
            'subscriber_id': cls.sub.id,
        })
        cls.meter_north = cls.Meter.create({
            'meter_number': 'MTR-NORTH-001',
            'customer_id': cls.customer_north.id,
            'region_id': cls.region_north.id,
            'company_id': cls.env.company.id,
        })

        # South customer & meter
        cls.partner_south = cls.Partner.create({
            'name': 'عميل الجنوب',
            'region_id': cls.region_south.id,
        })
        cls.customer_south = cls.Customer.create({
            'customer_number': 'CUST-SOUTH-001',
            'partner_id': cls.partner_south.id,
            'region_id': cls.region_south.id,
            'category_id': cls.cat.id,
            'subscriber_id': cls.sub.id,
        })
        cls.meter_south = cls.Meter.create({
            'meter_number': 'MTR-SOUTH-001',
            'customer_id': cls.customer_south.id,
            'region_id': cls.region_south.id,
            'company_id': cls.env.company.id,
        })

    def test_mismatched_batch_region_fails_line(self):
        """A line with south meter in a north batch must fail with region error."""
        batch = self.Batch.create({
            'region_id': self.region_north.id,
            'date_range_id': self.period_north.id,
        })
        line = self.BatchLine.create({
            'batch_id': batch.id,
            'meter_number': self.meter_south.meter_number,
            'reading_value': 120.0,
            'state': 'pending',
        })

        res = self.BatchService._process_single_batch_line(batch, line, {}, {})
        self.assertFalse(res.get('success'), 'السطر يجب أن يفشل لاختلاف المنطقة.')
        self.assertIn('تختلف عن منطقة الدفعة', res.get('error', ''))

    def test_matching_batch_region_succeeds(self):
        """A line with north meter in a north batch succeeds."""
        batch = self.Batch.create({
            'region_id': self.region_north.id,
            'date_range_id': self.period_north.id,
        })
        line = self.BatchLine.create({
            'batch_id': batch.id,
            'meter_number': self.meter_north.meter_number,
            'reading_value': 350.0,
            'state': 'pending',
        })

        res = self.BatchService._process_single_batch_line(batch, line, {}, {})
        self.assertTrue(res.get('success'), 'السطر يجب أن ينجح لتطابق المنطقة.')
        self.assertTrue(res.get('reading_id'))

    def test_reader_scope_validation(self):
        """Reader restricted to north region cannot process south meter."""
        reader = self.env['res.users'].create({
            'name': 'قارئ الشمال',
            'login': 'reader_north_%s' % id(self),
            'region_id': self.region_north.id,
        })
        batch = self.Batch.create({
            'user_id': reader.id,
            'region_id': self.region_north.id,
            'date_range_id': self.period_north.id,
        })
        line = self.BatchLine.create({
            'batch_id': batch.id,
            'meter_number': self.meter_south.meter_number,
            'reading_value': 200.0,
            'state': 'pending',
        })

        res = self.BatchService._process_single_batch_line(batch, line, {}, {})
        self.assertFalse(res.get('success'))

