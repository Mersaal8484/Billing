from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestMeterReplacementReading(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'مشترك استبدال عداد اختبار',
        })
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'فئة تجاري',
            'code': 'COM_TEST',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'محل تجاري',
            'category_id': self.category.id,
        })
        self.old_meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-OLD-999',
            'multiplier': 1.0,
        })
        self.new_meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-NEW-888',
            'multiplier': 1.0,
        })
        self.customer = self.env['utility.customer'].create({
            'customer_number': 'CUST-REPL-001',
            'partner_id': self.partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'meter_id': self.old_meter.id,
            'last_invoice_reading': 100.0,
            'last_reading_value': 100.0,
        })

    def test_meter_replacement_creates_closing_and_opening_readings(self):
        """التحقق من إنشاء القراءة الختامية والقراءة الافتتاحية عند تأكيد استبدال العداد"""
        replacement = self.env['utility.meter.replacement'].create({
            'utility_account_id': self.customer.id,
            'old_meter_id': self.old_meter.id,
            'old_last_invo_reading': 100.0,
            'old_closing_reading': 180.0,
            'new_meter_id': self.new_meter.id,
            'new_opening_reading': 10.0,
            'reason': 'fault',
        })

        # التحقق من حساب الاستهلاك غير المفوتر
        self.assertEqual(replacement.old_uninvoiced_consumption, 80.0)

        # تأكيد الاستبدال
        replacement.action_confirm_replacement()

        # التحقق من تغيير الحالة وإنشاء القراءات
        self.assertEqual(replacement.state, 'done')
        self.assertTrue(replacement.closing_reading_id)
        self.assertTrue(replacement.opening_reading_id)

        # التحقق من بيانات القراءة الختامية
        closing = replacement.closing_reading_id
        self.assertEqual(closing.reading_purpose, 'replacement_closing')
        self.assertEqual(closing.reading_value, 180.0)
        self.assertEqual(closing.meter_id, self.old_meter)
        self.assertEqual(closing.state, 'approved')

        # التحقق من بيانات القراءة الافتتاحية
        opening = replacement.opening_reading_id
        self.assertEqual(opening.reading_purpose, 'opening')
        self.assertEqual(opening.reading_value, 10.0)
        self.assertEqual(opening.meter_id, self.new_meter)
        self.assertTrue(opening.is_initial_reading)

        # التحقق من تغيير العداد على حساب المشترك
        self.assertEqual(self.customer.meter_id, self.new_meter)

    def test_invalid_closing_reading_raises_validation(self):
        """التحقق من رفض قراءة ختامية أقل من آخر قراءة مفوترة"""
        replacement = self.env['utility.meter.replacement'].create({
            'utility_account_id': self.customer.id,
            'old_meter_id': self.old_meter.id,
            'old_last_invo_reading': 100.0,
            'old_closing_reading': 50.0,  # قراءة سالبة / أقل من المفوترة
            'new_meter_id': self.new_meter.id,
            'new_opening_reading': 0.0,
            'reason': 'fault',
        })
        with self.assertRaises((UserError, ValidationError)):
            replacement.action_confirm_replacement()
