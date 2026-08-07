import base64
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError


class TestUtilityMediaAsset(TransactionCase):

    def setUp(self):
        super().setUp()
        self.MediaAsset = self.env['utility.media.asset']
        self.MediaService = self.env['utility.media.service']
        self.BatchService = self.env['utility.reading.batch.service']
        self.Region = self.env['utility.region']
        self.Meter = self.env['utility.meter']
        self.Customer = self.env['utility.customer']
        self.DateRange = self.env['date.range']
        self.Batch = self.env['utility.reading.batch']

        # تجهيز صورة تجريبية (100x100 Red Pixel JPEG)
        self.sample_base64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        self.sample_bytes = base64.b64decode(self.sample_base64)

        self.region = self.Region.create({
            'name': 'منطقة وسائط تجريبية',
            'code': 'REG-MEDIA-01',
            'type': 'region',
            'recurring_rule_type': 'monthly',
        })

    def test_01_media_storage_adapter_and_asset_creation(self):
        """1. اختبار تخزين صورة رقمية وتوليد النسخ الثلاث (Original, Review, Thumbnail) عبر Media Service"""
        asset = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="meter_read_01.jpg",
            mimetype="image/png",
            asset_type="meter_reading"
        )

        self.assertTrue(asset)
        self.assertEqual(asset.state, 'ready')
        self.assertTrue(asset.asset_uuid)
        self.assertTrue(asset.sha256)
        self.assertEqual(asset.storage_backend, 'attachment')
        self.assertTrue(asset.original_attachment_id)
        self.assertTrue(asset.review_attachment_id)
        self.assertTrue(asset.thumbnail_attachment_id)

        # استرجاع المحتوى عبر Adapter
        retrieved_orig = self.MediaService.retrieve_media(asset, variant='original')
        self.assertEqual(retrieved_orig, self.sample_bytes)

    def test_02_duplicate_media_asset_prevention(self):
        """2. اختبار منع تكرار التخزين الثنائي لنفس البصمة SHA256 وإعادة استخدام الأصل"""
        asset1 = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="meter_read_dup1.jpg",
            mimetype="image/png"
        )

        asset2 = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="meter_read_dup2.jpg",
            mimetype="image/png"
        )

        # عدم تكرار الإنشاء الثنائي وإعادة استخدام الأصل الأول
        self.assertEqual(asset1.id, asset2.id)

    def test_03_decoupled_batch_processing_and_error_isolation(self):
        """3. اختبار معالجة الدفعة عبر ReadingBatchService وعزل الأخطاء جزئياً (Partial Batch)"""
        period = self.DateRange.create({
            'name': 'فترة الوسائط',
            'period_code': 'R-MEDIA-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'region_ids': [(6, 0, [self.region.id])],
        })

        customer = self.Customer.create({
            'name': 'مشترك الوسائط',
            'customer_number': 'CUST-MEDIA-01',
            'region_id': self.region.id,
        })

        meter = self.Meter.create({
            'meter_number': 'MTR-MEDIA-01',
            'customer_id': customer.id,
        })

        # بيانات JSON تحتوى على عداد صحيح وعداد غير موجود (خطأ)
        payload = {
            'readings': [
                {
                    'seq': 1,
                    'meter_number': 'MTR-MEDIA-01',
                    'reading_value': 250.0,
                    'image_filename': 'img1.png',
                },
                {
                    'seq': 2,
                    'meter_number': 'MTR-INVALID-99',
                    'reading_value': 300.0,
                    'image_filename': 'img2.png',
                }
            ]
        }
        json_b64 = base64.b64encode(bytes(str(payload).replace("'", '"'), 'utf-8')).decode('utf-8')

        batch = self.Batch.create({
            'name': 'دفعة تجريبية عازلة للأخطاء',
            'region_id': self.region.id,
            'date_range_id': period.id,
            'data_file': json_b64,
            'state': 'uploaded',
        })

        # مرفق صورة تجريبية مرتبط بالدفعة
        self.env['ir.attachment'].create({
            'name': 'img1.png',
            'datas': self.sample_base64,
            'res_model': 'utility.reading.batch',
            'res_id': batch.id,
        })

        # تشغيل المعالجة المستقلة
        res = self.BatchService.process_batch(batch.id)
        self.assertEqual(res['status'], 'completed')
        self.assertEqual(res['success_count'], 1)
        self.assertEqual(res['error_count'], 1)

        # التحقق من إنشاء القراءة وربطها بالأصل الرقمي
        reading = self.env['utility.reading'].search([('batch_id', '=', batch.id)], limit=1)
        self.assertTrue(reading)
        self.assertTrue(reading.image_asset_id)
        self.assertEqual(reading.image_asset_id.state, 'ready')

    def test_04_user_media_access_security(self):
        """4. اختبار فحص الأمن والتحقق من صلاحية الوصول الرقمي للأصل"""
        asset = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="security_test.jpg",
            mimetype="image/png"
        )

        # المستخدم الحالي أدمن للنظام يملك الصلاحية
        self.assertTrue(asset.check_user_access_security(self.env.user))
