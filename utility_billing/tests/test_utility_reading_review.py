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

        # 1. إنشاء منطقة وسجل مشترك وعداد للاختبار
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

        # إنشاء فترة قراءة
        range_type = self.env['date.range.type'].search([], limit=1)
        if not range_type:
            range_type = self.env['date.range.type'].create({'name': 'شهري', 'work_type': 'readings'})

        self.test_period = self.DateRange.create({
            'name': 'فترة مراجعة القراءات 2026-08',
            'type_id': range_type.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
        })

    def test_01_get_review_queue_pagination(self):
        """1. اختبار طابور المراجعة وتقسيم الصفحات إلى 40 عنصر"""
        # إنشاء 45 قراءة اختبارية
        readings_vals = []
        for i in range(45):
            readings_vals.append({
                'meter_id': self.test_meter.id,
                'account_id': self.test_customer.id,
                'reading_date': fields.Datetime.now(),
                'reading_value': 1000 + (i * 10),
                'state': 'under_review',
                'date_range_id': self.test_period.id,
            })
        self.Reading.create(readings_vals)

        # جلب الصفحة الأولى (limit=40)
        res_p1 = self.ReadingReviewService.get_review_queue(
            period_id=self.test_period.id,
            status='under_review',
            offset=0,
            limit=40
        )

        self.assertEqual(res_p1['pagination']['page_size'], 40)
        self.assertEqual(len(res_p1['items']), 40)
        self.assertGreaterEqual(res_p1['pagination']['total'], 45)
        self.assertEqual(res_p1['pagination']['pages'], 2)

        # جلب الصفحة الثانية (offset=40)
        res_p2 = self.ReadingReviewService.get_review_queue(
            period_id=self.test_period.id,
            status='under_review',
            offset=40,
            limit=40
        )
        self.assertEqual(len(res_p2['items']), 5)
        self.assertEqual(res_p2['pagination']['page'], 2)

    def test_02_action_approve_review(self):
        """2. اختبار دالة اعتماد القراءات وتسجيل بيانات المراجع"""
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
        """3. اختبار دالة رفض القراءات وتسجيل السبب"""
        reading = self.Reading.create({
            'meter_id': self.test_meter.id,
            'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': 3000,
            'state': 'under_review',
            'date_range_id': self.test_period.id,
        })

        res = self.ReadingReviewService.action_reject_review(
            [reading.id],
            rejection_reason='الصورة غير واضحة',
            review_notes='يرجى إعادة التصوير'
        )
        self.assertEqual(res['status'], 'success')
        self.assertEqual(reading.state, 'draft')
        self.assertEqual(reading.rejection_reason, 'الصورة غير واضحة')
        self.assertEqual(reading.review_notes, 'يرجى إعادة التصوير')

    def test_04_action_bulk_approve_safe(self):
        """4. اختبار الاعتماد الجملي الآمن للقراءات السليمة"""
        r1 = self.Reading.create({
            'meter_id': self.test_meter.id,
            'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': 4000,
            'state': 'under_review',
            'image_state': 'clear',
            'date_range_id': self.test_period.id,
        })
        r2 = self.Reading.create({
            'meter_id': self.test_meter.id,
            'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': 4100,
            'state': 'under_review',
            'image_state': 'not_clear', # غير سليمة - يجب استبعادها من الاعتماد الجملي
            'date_range_id': self.test_period.id,
        })

        res = self.ReadingReviewService.action_bulk_approve_safe([r1.id, r2.id])
        self.assertEqual(res['status'], 'success')
        self.assertEqual(r1.state, 'approved')
        self.assertEqual(r2.state, 'under_review') # بقيت قيد المراجعة للحماية

    def test_05_reading_semantics_and_is_billable(self):
        """5. اختبار الأبعاد الثلاثة للقراءة والتحقق من حساب is_billable"""
        # Periodic Customer Reading -> Billable
        r_cust = self.Reading.create({
            'meter_id': self.test_meter.id,
            'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': 5000,
            'reading_category': 'customer',
            'reading_purpose': 'periodic',
            'reading_event': 'normal',
        })
        self.assertTrue(r_cust.is_billable)

        # Opening Customer Reading -> Not billable (Baseline)
        r_open = self.Reading.create({
            'meter_id': self.test_meter.id,
            'account_id': self.test_customer.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': 0,
            'reading_category': 'customer',
            'reading_purpose': 'opening',
            'reading_event': 'installation',
        })
        self.assertFalse(r_open.is_billable)

        # Public Transformer Reading -> Not billable
        trans_pub = self.env['utility.transformer'].create({
            'name': 'محول عام شبكي',
            'code': 'TR-PUB-01',
            'is_private': False,
        })
        meter_trans = self.Meter.create({
            'meter_number': 'MTR-TR-01',
            'linked_transformer_id': trans_pub.id,
        })
        r_trans = self.Reading.create({
            'meter_id': meter_trans.id,
            'transformer_id': trans_pub.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': 12000,
            'reading_category': 'transformer',
            'reading_purpose': 'periodic',
        })
        self.assertFalse(r_trans.is_billable)
