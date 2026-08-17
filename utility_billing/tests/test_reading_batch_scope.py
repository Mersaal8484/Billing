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
        cls.branch_north_a = cls.Region.create({
            'name': 'فرع الشمال أ',
            'code': 'NORTH-BR-A',
            'type': 'area',
            'parent_id': cls.region_north.id,
            'recurring_rule_type': 'monthly',
        })
        cls.branch_north_b = cls.Region.create({
            'name': 'فرع الشمال ب',
            'code': 'NORTH-BR-B',
            'type': 'area',
            'parent_id': cls.region_north.id,
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

        # North customer & meter in Branch A
        cls.partner_north_a = cls.Partner.create({
            'name': 'عميل الشمال فرع أ',
            'region_id': cls.region_north.id,
        })
        cls.customer_north_a = cls.Customer.create({
            'customer_number': 'CUST-NORTH-A',
            'partner_id': cls.partner_north_a.id,
            'region_id': cls.region_north.id,
            'area_id': cls.branch_north_a.id,
            'category_id': cls.cat.id,
            'subscriber_id': cls.sub.id,
        })
        cls.meter_north_a = cls.Meter.create({
            'meter_number': 'MTR-NORTH-A',
            'customer_id': cls.customer_north_a.id,
            'region_id': cls.region_north.id,
            'area_id': cls.branch_north_a.id,
            'company_id': cls.env.company.id,
        })

        # North customer & meter in Branch B
        cls.partner_north_b = cls.Partner.create({
            'name': 'عميل الشمال فرع ب',
            'region_id': cls.region_north.id,
        })
        cls.customer_north_b = cls.Customer.create({
            'customer_number': 'CUST-NORTH-B',
            'partner_id': cls.partner_north_b.id,
            'region_id': cls.region_north.id,
            'area_id': cls.branch_north_b.id,
            'category_id': cls.cat.id,
            'subscriber_id': cls.sub.id,
        })
        cls.meter_north_b = cls.Meter.create({
            'meter_number': 'MTR-NORTH-B',
            'customer_id': cls.customer_north_b.id,
            'region_id': cls.region_north.id,
            'area_id': cls.branch_north_b.id,
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
            'meter_number': self.meter_north_a.meter_number,
            'reading_value': 350.0,
            'state': 'pending',
        })

        res = self.BatchService._process_single_batch_line(batch, line, {}, {})
        self.assertTrue(res.get('success'), 'السطر يجب أن ينجح لتطابق المنطقة.')
        self.assertTrue(res.get('reading_id'))

    def test_closed_period_fails_line(self):
        """Processing a reading line in a closed period must fail."""
        closed_period = self.env['date.range'].create({
            'name': 'فترة الشمال المغلقة',
            'period_code': 'NORTH-2026-07',
            'cycle_key': 'NORTH-2026-07',
            'period_role': 'reading',
            'type_id': self.range_type.id,
            'region_ids': [(6, 0, [self.region_north.id])],
            'date_start': '2026-07-01',
            'date_end': '2026-07-31',
            'billing_cadence': 'monthly',
            'state': 'closed',
        })
        batch = self.Batch.create({
            'region_id': self.region_north.id,
            'date_range_id': closed_period.id,
        })
        line = self.BatchLine.create({
            'batch_id': batch.id,
            'meter_number': self.meter_north_a.meter_number,
            'reading_value': 180.0,
            'state': 'pending',
        })

        res = self.BatchService._process_single_batch_line(batch, line, {}, {})
        self.assertFalse(res.get('success'), 'السطر يجب أن يفشل لأن الفترة مغلقة.')
        self.assertIn('ليست في حالة مفتوحة', res.get('error', ''))

    def test_reader_scope_branch_authorization(self):
        """Reader restricted to Branch A cannot process Meter B in Branch B (same North region)."""
        reader_branch_a = self.env['res.users'].create({
            'name': 'قارئ فرع أ فقط',
            'login': 'reader_br_a_%s' % id(self),
            'scope_mode': 'restricted',
            'assigned_branch_ids': [(6, 0, [self.branch_north_a.id])],
        })
        batch = self.Batch.create({
            'user_id': reader_branch_a.id,
            'region_id': self.region_north.id,
            'date_range_id': self.period_north.id,
        })
        # Line for Meter B (in Branch B)
        line = self.BatchLine.create({
            'batch_id': batch.id,
            'meter_number': self.meter_north_b.meter_number,
            'reading_value': 220.0,
            'state': 'pending',
        })

        res = self.BatchService._process_single_batch_line(batch, line, {}, {})
        self.assertFalse(res.get('success'), 'القارئ المخصص للفرع أ لا يمكنه معالجة عداد في الفرع ب.')
        self.assertIn('خارج النطاق الجغرافي/التنظيمي المخصص للقارئ', res.get('error', ''))

    def test_global_reader_allowed_across_branches(self):
        """Global reader can process meters in any branch of the region."""
        global_reader = self.env['res.users'].create({
            'name': 'قارئ شامل',
            'login': 'reader_global_%s' % id(self),
            'scope_mode': 'global',
        })
        batch = self.Batch.create({
            'user_id': global_reader.id,
            'region_id': self.region_north.id,
            'date_range_id': self.period_north.id,
        })
        line_a = self.BatchLine.create({
            'batch_id': batch.id,
            'meter_number': self.meter_north_a.meter_number,
            'reading_value': 410.0,
            'state': 'pending',
        })
        line_b = self.BatchLine.create({
            'batch_id': batch.id,
            'meter_number': self.meter_north_b.meter_number,
            'reading_value': 520.0,
            'state': 'pending',
        })

        res_a = self.BatchService._process_single_batch_line(batch, line_a, {}, {})
        res_b = self.BatchService._process_single_batch_line(batch, line_b, {}, {})
        self.assertTrue(res_a.get('success'), 'القارئ الشامل يجب أن ينجح في الفرع أ.')
        self.assertTrue(res_b.get('success'), 'القارئ الشامل يجب أن ينجح في الفرع ب.')
