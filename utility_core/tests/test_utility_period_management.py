from datetime import date, datetime, timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TestUtilityPeriodManagement(TransactionCase):
    """مجموعة اختبارات شاملة للهيكلية الجديدة لإدارة فترات القراءة والاستهلاك والسداد"""

    def setUp(self):
        super().setUp()
        self.DateRange = self.env['date.range'].sudo()
        self.Region = self.env['utility.region'].sudo()
        self.Customer = self.env['utility.customer'].sudo()
        self.Meter = self.env['utility.meter'].sudo()
        self.Reading = self.env['utility.reading'].sudo()
        self.Batch = self.env['utility.reading.batch'].sudo()
        self.SaleOrder = self.env['sale.order'].sudo()
        self.Generator = self.env['utility.period.generator'].sudo()

        # إنشاء مناطق باختبارات تكرار مختلفة
        self.region_monthly = self.Region.create({
            'name': 'منطقة صنعاء (شهري)',
            'code': 'SANAA_M',
            'type': 'region',
            'recurring_rule_type': 'monthly',
        })
        self.region_semi = self.Region.create({
            'name': 'منطقة تعز (نصف شهري)',
            'code': 'TAIZ_S',
            'type': 'region',
            'recurring_rule_type': 'semi_monthly',
        })

        # إنشاء فئات وقوالب مشاطرة
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'منزلي اختبار',
            'code': 'DOM_TEST',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'منزلي عادي',
            'code': 'DOM_NORM',
            'category_id': self.category.id,
        })
        self.template_monthly = self.env['utility.contract.template'].create({
            'name': 'عقد شهري',
            'code': 'TMP_M',
            'recurring_rule_type': 'monthly',
            'subscriber_category_ids': [(6, 0, [self.category.id])],
            'subscriber_ids': [(6, 0, [self.subscriber_type.id])],
            'scope': 'global',
        })
        self.template_semi = self.env['utility.contract.template'].create({
            'name': 'عقد نصف شهري',
            'code': 'TMP_S',
            'recurring_rule_type': 'semi_monthly',
            'subscriber_category_ids': [(6, 0, [self.category.id])],
            'subscriber_ids': [(6, 0, [self.subscriber_type.id])],
            'scope': 'global',
        })

        # حسابات ومشتركين
        self.partner = self.env['res.partner'].create({'name': 'مشترك اختبار 1'})
        self.customer_m = self.Customer.create({
            'name': 'حساب شهري',
            'partner_id': self.partner.id,
            'region_id': self.region_monthly.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'contract_template_id': self.template_monthly.id,
        })
        self.customer_s = self.Customer.create({
            'name': 'حساب نصف شهري',
            'partner_id': self.partner.id,
            'region_id': self.region_semi.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'contract_template_id': self.template_semi.id,
        })

        self.meter_m = self.Meter.create({
            'meter_number': 'MTR-M-001',
            'customer_id': self.customer_m.id,
        })
        self.meter_s = self.Meter.create({
            'meter_number': 'MTR-S-001',
            'customer_id': self.customer_s.id,
        })

    def test_01_monthly_region_period_filtering(self):
        """1. المنطقة الشهرية تختار الفترات الشهرية فقط"""
        domain_m = self.Reading._get_open_period_domain(work_type='readings', billing_period='monthly', region_id=self.region_monthly.id)
        self.assertIn(('billing_cadence', '=', 'monthly'), domain_m)

    def test_02_semi_monthly_region_period_filtering(self):
        """2. المنطقة نصف الشهرية تختار فترات H1/H2 فقط"""
        domain_s = self.Reading._get_open_period_domain(work_type='readings', billing_period='semi_monthly', region_id=self.region_semi.id)
        self.assertIn(('billing_cadence', '=', 'semi_monthly'), domain_s)

    def test_03_04_05_period_generator_h1_h2_february(self):
        """3, 4, 5. مولد الفترات للنصف الأول (1-15) والثاني (16-نهاية الشهر) واختبار فبراير"""
        wizard = self.Generator.create({
            'year': 2026,
            'month': '2', # فبراير 2026 (28 يوم)
            'billing_cadence': 'semi_monthly',
        })
        wizard.action_generate_periods()

        p_h1 = self.DateRange.search([('period_code', '=', 'SEMI-2026-02-H1')])
        p_h2 = self.DateRange.search([('period_code', '=', 'SEMI-2026-02-H2')])

        self.assertTrue(p_h1)
        self.assertEqual(p_h1.consumption_start, date(2026, 2, 1))
        self.assertEqual(p_h1.consumption_end, date(2026, 2, 15))

        self.assertTrue(p_h2)
        self.assertEqual(p_h2.consumption_start, date(2026, 2, 16))
        self.assertEqual(p_h2.consumption_end, date(2026, 2, 28))

    def test_06_reading_after_consumption_within_window(self):
        """6. قبول قراءة مأخوذة بعد نهاية الاستهلاك طالما ضمن نافذة القراءة المسموحة"""
        period = self.DateRange.create({
            'name': 'أغسطس 2026 H1',
            'period_code': 'SEMI-TEST-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'consumption_start': date(2026, 8, 1),
            'consumption_end': date(2026, 8, 15),
            'reading_window_start': datetime(2026, 8, 13, 0, 0, 0),
            'reading_window_end': datetime(2026, 8, 18, 23, 59, 59),
            'region_ids': [(6, 0, [self.region_semi.id])],
            'state': 'reading_open',
        })

        reading_date = datetime(2026, 8, 17, 10, 0, 0) # بعد 15 أغسطس وقبل 18 أغسطس
        reading = self.Reading.create({
            'meter_id': self.meter_s.id,
            'account_id': self.customer_s.id,
            'date_range_id': period.id,
            'reading_value': 150.0,
            'reading_date': reading_date,
            'reading_purpose': 'periodic',
        })
        self.assertTrue(reading)

    def test_07_reading_outside_window_rejected(self):
        """7. رفض القراءة المأخوذة خارج نافذة القراءة المسموحة"""
        period = self.DateRange.create({
            'name': 'أغسطس 2026 H1 STRICT',
            'period_code': 'SEMI-TEST-02',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'consumption_start': date(2026, 8, 1),
            'consumption_end': date(2026, 8, 15),
            'reading_window_start': datetime(2026, 8, 13, 0, 0, 0),
            'reading_window_end': datetime(2026, 8, 18, 23, 59, 59),
            'region_ids': [(6, 0, [self.region_semi.id])],
            'state': 'reading_open',
        })

        late_reading_date = datetime(2026, 8, 20, 10, 0, 0) # بعد النافذة (18 أغسطس)
        with self.assertRaises(ValidationError):
            self.Reading.create({
                'meter_id': self.meter_s.id,
                'account_id': self.customer_s.id,
                'date_range_id': period.id,
                'reading_value': 200.0,
                'reading_date': late_reading_date,
                'reading_purpose': 'periodic',
            })

    def test_08_batch_upload_within_upload_window(self):
        """8. رفع دفعة بعد نهاية الاستهلاك لكن ضمن نافذة الرفع المسموحة"""
        period = self.DateRange.create({
            'name': 'أغسطس 2026 H1 الدفعة',
            'period_code': 'SEMI-BATCH-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'consumption_start': date(2026, 8, 1),
            'consumption_end': date(2026, 8, 15),
            'reading_window_start': datetime(2026, 8, 13, 0, 0, 0),
            'reading_window_end': datetime(2026, 8, 18, 23, 59, 59),
            'region_ids': [(6, 0, [self.region_semi.id])],
            'state': 'reading_open',
        })

        batch = self.Batch.create({
            'date_range_id': period.id,
            'region_id': self.region_semi.id,
            'upload_date': datetime(2026, 8, 17, 14, 0, 0),
        })
        self.assertTrue(batch)

    def test_09_wrong_region_period_combination_rejected(self):
        """9. رفض اقتران منطقة غير مشمولة في نطاق مناطق الفترة"""
        period = self.DateRange.create({
            'name': 'فترة منطقة تعز فقط',
            'period_code': 'SEMI-REGION-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'region_ids': [(6, 0, [self.region_semi.id])],
        })

        with self.assertRaises(ValidationError):
            self.Batch.create({
                'date_range_id': period.id,
                'region_id': self.region_monthly.id, # منطقة صنعاء غير مشمولة
            })

    def test_10_wrong_cadence_combination_rejected(self):
        """10. رفض اقتران دورية منطقة لا تطابق دورية الفترة"""
        period = self.DateRange.create({
            'name': 'فترة نصف شهرية',
            'period_code': 'SEMI-CADENCE-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
        })

        with self.assertRaises(ValidationError):
            self.Batch.create({
                'date_range_id': period.id,
                'region_id': self.region_monthly.id, # دورية صنعاء شهري بينما الفترة نصف شهرية
            })

    def test_11_reading_closes_payment_remains_open(self):
        """11. إغلاق فترة القراءة لا يغلق فترة السداد والتحصيل المرتبطة"""
        r_period = self.DateRange.create({
            'name': 'قراءة H1',
            'period_code': 'R-SEMI-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'state': 'reading_open',
        })
        p_period = self.DateRange.create({
            'name': 'تحصيل H1',
            'period_code': 'PAY-SEMI-01',
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'reading_period_id': r_period.id,
            'state': 'payment_open',
        })

        r_period.action_close_reading()
        self.assertEqual(r_period.state, 'reading_closed')
        self.assertEqual(p_period.state, 'payment_open')

    def test_12_new_reading_opens_previous_payment_remains_open(self):
        """12. فتح فترة قراءة جديدة لا يغلق فترة التحصيل السابقة"""
        r_h1 = self.DateRange.create({
            'name': 'قراءة H1',
            'period_code': 'R-H1',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'state': 'closed',
        })
        p_h1 = self.DateRange.create({
            'name': 'تحصيل H1',
            'period_code': 'PAY-H1',
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'reading_period_id': r_h1.id,
            'state': 'payment_open',
        })

        r_h2 = self.DateRange.create({
            'name': 'قراءة H2',
            'period_code': 'R-H2',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'state': 'planned',
        })
        r_h2.action_open_reading()

        self.assertEqual(r_h2.state, 'reading_open')
        self.assertEqual(p_h1.state, 'payment_open')

    def test_13_overlapping_payment_periods(self):
        """13. تداخل وتزامن فترتي سداد وتحصيل مفتوحتين في الوقت نفسه"""
        r1 = self.DateRange.create({
            'name': 'قراءة H1',
            'period_code': 'R-OVERLAP-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
        })
        r2 = self.DateRange.create({
            'name': 'قراءة H2',
            'period_code': 'R-OVERLAP-02',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
        })

        p1 = self.DateRange.create({
            'name': 'تحصيل H1',
            'period_code': 'PAY-OVERLAP-01',
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'reading_period_id': r1.id,
            'state': 'payment_open',
        })
        p2 = self.DateRange.create({
            'name': 'تحصيل H2',
            'period_code': 'PAY-OVERLAP-02',
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'reading_period_id': r2.id,
            'state': 'payment_open',
        })

        self.assertEqual(p1.state, 'payment_open')
        self.assertEqual(p2.state, 'payment_open')

    def test_14_monthly_and_semi_monthly_concurrent(self):
        """14. عمل واستمرار الفترات الشهرية ونصف الشهرية بالتزامن الاستقلالي"""
        m_period = self.DateRange.create({
            'name': 'قراءة صنعاء شهري',
            'period_code': 'R-CONC-M',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'region_ids': [(6, 0, [self.region_monthly.id])],
            'state': 'reading_open',
        })

        s_period = self.DateRange.create({
            'name': 'قراءة تعز نصف شهري',
            'period_code': 'R-CONC-S',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'region_ids': [(6, 0, [self.region_semi.id])],
            'state': 'reading_open',
        })

        self.assertEqual(m_period.state, 'reading_open')
        self.assertEqual(s_period.state, 'reading_open')

    def test_15_closing_reading_does_not_stop_collection(self):
        """15. إغلاق فترة القراءة لا يوقف عمليات التحصيل المالي للفواتير المنشأة"""
        r_period = self.DateRange.create({
            'name': 'قراءة أغسطس',
            'period_code': 'R-COLL-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'state': 'reading_open',
        })
        p_period = self.DateRange.create({
            'name': 'تحصيل أغسطس',
            'period_code': 'PAY-COLL-01',
            'period_role': 'payment',
            'billing_cadence': 'monthly',
            'reading_period_id': r_period.id,
            'state': 'payment_open',
        })

        r_period.action_close_reading()
        self.assertEqual(p_period.state, 'payment_open')

    def test_16_opening_next_reading_does_not_close_previous_payment(self):
        """16. فتح فترة قراءة تالية لا يغلق تلقائياً فترة تحصيل الدورة السابقة"""
        r_aug = self.DateRange.create({
            'name': 'قراءة أغسطس H1',
            'period_code': 'R-AUG-H1',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'state': 'closed',
        })
        p_aug = self.DateRange.create({
            'name': 'تحصيل أغسطس H1',
            'period_code': 'PAY-AUG-H1',
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'reading_period_id': r_aug.id,
            'state': 'payment_open',
        })

        r_sep = self.DateRange.create({
            'name': 'قراءة أغسطس H2',
            'period_code': 'R-AUG-H2',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'state': 'planned',
        })
        r_sep.action_open_reading()

        self.assertEqual(p_aug.state, 'payment_open')
        self.assertEqual(r_sep.state, 'reading_open')

    def test_17_late_payment_controlled_accounting_flow(self):
        """17. قبول السداد المتأخر عبر النظام المحاسبي وتصنيفه كـ late"""
        r_period = self.DateRange.create({
            'name': 'قراءة H1 لغرض التحصيل المتأخر',
            'period_code': 'R-LATE-PAY',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'region_ids': [(6, 0, [self.region_semi.id])],
            'state': 'reading_open',
        })
        p_period = self.DateRange.create({
            'name': 'تحصيل H1 مغلق',
            'period_code': 'PAY-LATE-PAY',
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'reading_period_id': r_period.id,
            'payment_window_start': datetime(2026, 8, 16, 0, 0, 0),
            'payment_window_end': datetime(2026, 8, 25, 23, 59, 59),
            'state': 'closed',
        })

        reading = self.Reading.create({
            'meter_id': self.meter_s.id,
            'account_id': self.customer_s.id,
            'date_range_id': r_period.id,
            'reading_value': 300.0,
            'reading_date': datetime(2026, 8, 15, 10, 0, 0),
            'reading_purpose': 'periodic',
            'state': 'approved',
        })

        res = reading.action_generate_bill()
        order = self.SaleOrder.browse(res['res_id'])

        payment = self.env['account.payment'].create({
            'utility_sale_order_id': order.id,
            'partner_id': self.partner.id,
            'amount': order.amount_total,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'date': date(2026, 8, 28), # تاريخ بعد نهاية النافذة (25 أغسطس)
        })
        payment.action_post()

        self.assertEqual(payment.state, 'posted')
        self.assertEqual(payment.timing_classification, 'late')

    def test_18_late_reading_does_not_reassign_period(self):
        """18. القراءة المتأخرة تحتفظ بفترتها الأصلية ولا تُرحل تلقائياً للفترة التالية"""
        p_orig = self.DateRange.create({
            'name': 'فترة الاستهلاك الأصلية H1',
            'period_code': 'R-ORIG-H1',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'consumption_start': date(2026, 8, 1),
            'consumption_end': date(2026, 8, 15),
            'reading_window_start': datetime(2026, 8, 13, 0, 0, 0),
            'reading_window_end': datetime(2026, 8, 30, 23, 59, 59),
            'region_ids': [(6, 0, [self.region_semi.id])],
            'state': 'reading_open',
        })

        reading = self.Reading.create({
            'meter_id': self.meter_s.id,
            'account_id': self.customer_s.id,
            'date_range_id': p_orig.id,
            'reading_value': 500.0,
            'reading_date': datetime(2026, 8, 25, 10, 0, 0), # مأخوذة متأخراً
            'reading_purpose': 'periodic',
        })

        self.assertEqual(reading.date_range_id, p_orig)

    def test_19_duplicate_billable_reading_prevented(self):
        """19. منع إنشاء أكثر من قراءة دورية واحدة للحساب والفترة نفسها"""
        period = self.DateRange.create({
            'name': 'فترة تكرار',
            'period_code': 'R-DUP-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'region_ids': [(6, 0, [self.region_monthly.id])],
            'state': 'reading_open',
        })

        self.Reading.create({
            'meter_id': self.meter_m.id,
            'account_id': self.customer_m.id,
            'date_range_id': period.id,
            'reading_value': 100.0,
            'reading_purpose': 'periodic',
        })

        with self.assertRaises(ValidationError):
            self.Reading.create({
                'meter_id': self.meter_m.id,
                'account_id': self.customer_m.id,
                'date_range_id': period.id,
                'reading_value': 120.0,
                'reading_purpose': 'periodic',
            })

    def test_20_duplicate_bill_generation_prevented(self):
        """20. منع إنشاء أكثر من فاتورة نشطة واحدة لنفس المشترك والفترة"""
        period = self.DateRange.create({
            'name': 'فترة منع تكرار الفاتورة',
            'period_code': 'R-DUP-BILL-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'region_ids': [(6, 0, [self.region_monthly.id])],
            'state': 'reading_open',
        })

        reading1 = self.Reading.create({
            'meter_id': self.meter_m.id,
            'account_id': self.customer_m.id,
            'date_range_id': period.id,
            'reading_value': 100.0,
            'reading_purpose': 'periodic',
            'state': 'approved',
        })

        res = reading1.action_generate_bill()
        self.assertTrue(res.get('res_id'))

        # محاولة إنشاء أمر بيع آخر يدوي لنفس المشترك والفترة
        with self.assertRaises(ValidationError):
            self.SaleOrder.create({
                'partner_id': self.partner.id,
                'customer_id': self.customer_m.id,
                'meter_id': self.meter_m.id,
                'date_range_id': period.id,
                'reading_id': reading1.id,
            })

    def test_21_workflow_adapter_execution(self):
        """21. محاكاة تشغيل مسار العمل عبر LocalWorkflowAdapter"""
        period = self.DateRange.create({
            'name': 'فترة اختبار Workflow Service',
            'period_code': 'R-WF-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'state': 'planned',
        })

        service = self.env['utility.workflow.service']

        res1 = service.trigger_reading_period_workflow(period.id)
        self.assertEqual(res1['status'], 'started')
        self.assertEqual(res1['adapter'], 'local')
        w_id1 = period.workflow_id

        # إعادة الاستدعاء لا تخلق فترات مكررة أو تكسر الحالة
        res2 = service.trigger_reading_period_workflow(period.id)
        self.assertEqual(res2['status'], 'started')
        self.assertEqual(period.workflow_id, w_id1)

    def test_22_period_cannot_finalize_with_unresolved_errors(self):
        """22. منع إغلاق الفترة إذا كانت تحتوي على قراءات معلقة أو لم تكتمل فوترتها"""
        period = self.DateRange.create({
            'name': 'فترة إغلاق غير مكتملة',
            'period_code': 'R-UNRES-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'state': 'accounting',
        })

        # إنشاء قراءة غير معتمدة داخل الفترة
        self.Reading.create({
            'meter_id': self.meter_m.id,
            'account_id': self.customer_m.id,
            'date_range_id': period.id,
            'reading_value': 100.0,
            'reading_purpose': 'periodic',
            'state': 'under_review',
        })

        with self.assertRaises(ValidationError):
            period.action_close_period()

    def test_23_period_reopening_audited(self):
        """23. تدقيق وتسجيل إعادة فتح الفترة استثنائياً في سجل التدقيق"""
        period = self.DateRange.create({
            'name': 'فترة إعادة فتح',
            'period_code': 'R-REOPEN-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'state': 'closed',
        })

        period.action_reopen_period(reason="إعادة فتح لتصحيح قراءة خاطئة")
        self.assertEqual(period.state, 'reading_open')
        self.assertTrue(period.log_ids)
        self.assertEqual(period.log_ids[0].new_state, 'reading_open')
        self.assertIn("تصحيح قراءة", period.log_ids[0].reason)

    def test_24_historical_period_cadence_immutable(self):
        """24. تغيير دورية المنطقة لاحقاً لا يُعدل دورية الفترات أو المستندات التاريخية المنشأة سابقاً"""
        period = self.DateRange.create({
            'name': 'فترة تعز تاريخية',
            'period_code': 'R-HIST-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'region_ids': [(6, 0, [self.region_semi.id])],
        })

        # تغيير دورية المنطقة من نصف شهري إلى شهري
        self.region_semi.write({'recurring_rule_type': 'monthly'})

        # الفترة التاريخية المنشأة سابقاً تظل محتفظة بدوريتها الأصيلة
        self.assertEqual(period.billing_cadence, 'semi_monthly')

    def test_25_invalid_state_transition_prevented(self):
        """25. منع القفز غير التسلسلي بين حالات الفترة بواسطة مصفوفة التحول (Transition Matrix)"""
        period = self.DateRange.create({
            'name': 'فترة اختراق الحالات',
            'period_code': 'R-TRANS-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'state': 'planned',
        })

        # محاولة القفز المباشر من مخطط إلى الفوترة ينبغي أن تُرفض
        with self.assertRaises(ValidationError):
            period.action_start_billing()

        # فتح القراءة أولاً
        period.action_open_reading()
        self.assertEqual(period.state, 'reading_open')

        # محاولة القفز المباشر من نافذة القراءة مفتوحة إلى التظهير المحاسبي ينبغي أن تُرفض
        with self.assertRaises(ValidationError):
            period.action_start_accounting()

    def test_26_biweekly_region_cadence_normalization(self):
        """26. توحيد وقبول المنطقة ذات الدورية القديمة biweekly مع فترات semi_monthly دون خطأ تضارب"""
        region_bw = self.env['utility.region'].create({
            'name': 'منطقة دورية قديمة',
            'code': 'REG-BW',
            'type': 'region',
            'recurring_rule_type': 'biweekly',
        })

        # ربط المنطقة القديمة بفترة نصف شهرية يجب أن ينجح بسبب الـ normalization
        period = self.DateRange.create({
            'name': 'فترة نصف شهرية لمنطقة biweekly',
            'period_code': 'R-NORM-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'region_ids': [(6, 0, [region_bw.id])],
        })
        self.assertEqual(period.billing_cadence, 'semi_monthly')

    def test_27_durable_outbox_queue_and_idempotency(self):
        """27. تسجيل وتتبع أوامر مسارات العمل في طابور Outbox مع مفتاح عدم التكرار (Idempotency Key)"""
        period = self.DateRange.create({
            'name': 'فترة طابور الأوامر',
            'period_code': 'R-OUTBOX-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'state': 'planned',
        })

        service = self.env['utility.workflow.service']
        res = service.execute_open_reading_window(period.id)
        self.assertTrue(res)
        self.assertEqual(period.state, 'reading_open')

        # التحقق من وجود أمر مسجل في Outbox بحالة executed
        cmd = self.env['utility.workflow.command'].search([('period_id', '=', period.id), ('action_type', '=', 'open_reading_window')], limit=1)
        self.assertTrue(cmd)
        self.assertEqual(cmd.state, 'executed')
        self.assertTrue(cmd.command_uuid)
        self.assertTrue(cmd.idempotency_key)
        self.assertGreater(cmd.attempt_count, 0)
        self.assertTrue(cmd.started_at)
        self.assertTrue(cmd.completed_at)
