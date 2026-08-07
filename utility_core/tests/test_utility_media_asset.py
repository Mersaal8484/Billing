import base64
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, ValidationError


class TestUtilityMediaAsset(TransactionCase):

    def setUp(self):
        super().setUp()
        self.MediaAsset = self.env['utility.media.asset']
        self.MediaService = self.env['utility.media.service']
        self.BatchService = self.env['utility.reading.batch.service']
        self.WorkflowService = self.env['utility.workflow.service']
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
            'name': 'منطقة وسائط A1+++',
            'code': 'REG-MEDIA-A1PPP',
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

    def test_02_duplicate_media_binary_deduplication(self):
        """2. اختبار إعادة استخدام المرفق الثنائي دون إنشاء سجلات مرفقات متكررة مع إنشاء أصل مستقل لكل إثبات"""
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

        # إنشاء سجل أصل إثبات منفصل لكل قراءة مع إعادة استخدام المرفق الثنائي الأصلي لعدم تكرار التخزين
        self.assertNotEqual(asset1.id, asset2.id)
        self.assertEqual(asset1.original_attachment_id.id, asset2.original_attachment_id.id)

    def test_03_canonical_image_asset_id_and_meter_image_non_stored_facade(self):
        """3. اختبار الحقل الأصيل image_asset_id والتوافقية غير المخزنة meter_image بدون تكرار الثنائي"""
        asset = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="meter_read_canonical.jpg",
            mimetype="image/png"
        )

        customer = self.Customer.create({
            'name': 'مشترك الوسائط Canonical A1+++',
            'customer_number': 'CUST-CANON-03',
            'region_id': self.region.id,
        })
        meter = self.Meter.create({
            'meter_number': 'MTR-CANON-03',
            'customer_id': customer.id,
        })

        reading = self.env['utility.reading'].create({
            'meter_id': meter.id,
            'account_id': customer.id,
            'reading_value': 100.0,
            'image_asset_id': asset.id,
        })

        self.assertEqual(reading.image_asset_id.id, asset.id)
        # التحقق من أن meter_image يقرأ تلقائياً عبر compute من الأصل الرقمي
        self.assertTrue(reading.meter_image)

    def test_04_decoupled_batch_processing_retry_and_under_review_state(self):
        """4. اختبار معالجة الدفعة وحماية التكرار والصور المصحوبة تحت المراجعة (under_review)"""
        period = self.DateRange.create({
            'name': 'فترة الوسائط A1+++',
            'period_code': 'R-MEDIA-A1PPP-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'region_ids': [(6, 0, [self.region.id])],
        })

        customer = self.Customer.create({
            'name': 'مشترك الدفعة A1+++',
            'customer_number': 'CUST-BATCH-A1PPP',
            'region_id': self.region.id,
        })

        meter = self.Meter.create({
            'meter_number': 'MTR-BATCH-A1PPP',
            'customer_id': customer.id,
        })

        payload = {
            'readings': [
                {
                    'seq': 1,
                    'meter_number': 'MTR-BATCH-A1PPP',
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
            'name': 'دفعة A1+++ عازلة للأخطاء',
            'region_id': self.region.id,
            'date_range_id': period.id,
            'data_file': json_b64,
            'state': 'uploaded',
        })

        self.assertTrue(batch.batch_uuid)

        # رفع أصل رقمي مسبق مرتبط بالدفعة باسم img1.png
        asset = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="img1.png",
            mimetype="image/png",
            batch_id=batch.id,
            asset_type="meter_reading"
        )

        # تأكيد الدفعة وتفويض الأمر عبر Workflow Command
        batch.action_confirm()

        # التحقق من أن حالة القراءة المصحوبة بصورة أصبحت under_review لمراجعة الصورة
        reading = self.env['utility.reading'].search([('batch_id', '=', batch.id)], limit=1)
        self.assertTrue(reading)
        self.assertEqual(reading.state, 'under_review')

        # التحقق من أن إعادة المحاولة action_reset_to_uploaded تنشئ command ببادئة RETRY:1
        batch.action_reset_to_uploaded()
        retry_key = f"READING-BATCH:{batch.batch_uuid}:RETRY:1"
        retry_cmd = self.env['utility.workflow.command'].search([('idempotency_key', '=', retry_key)], limit=1)
        self.assertTrue(retry_cmd)
        self.assertEqual(retry_cmd.state, 'executed')

    def test_05_user_media_access_security(self):
        """5. اختبار فحص الأمن والتحقق من صلاحية الوصول الرقمي للأصل"""
        asset = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="security_test.jpg",
            mimetype="image/png"
        )
        self.assertTrue(asset.check_user_access_security(self.env.user))

    def test_06_duplicate_confirm_idempotency_and_explicit_retry(self):
        """6. اختبار منع تكرار التأكيد (Duplicate Confirm Idempotency) والتفريق عن إعادة المحاولة الصريحة (Explicit Retry)"""
        period = self.DateRange.create({
            'name': 'فترة التكرار A1++++',
            'period_code': 'R-MEDIA-A1PPPP-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'region_ids': [(6, 0, [self.region.id])],
        })

        customer = self.Customer.create({
            'name': 'مشترك التكرار',
            'customer_number': 'CUST-DUP-01',
            'region_id': self.region.id,
        })
        meter = self.Meter.create({
            'meter_number': 'MTR-DUP-01',
            'customer_id': customer.id,
        })

        payload = {
            'readings': [
                {'seq': 1, 'meter_number': 'MTR-DUP-01', 'reading_value': 120.0}
            ]
        }
        json_b64 = base64.b64encode(bytes(str(payload).replace("'", '"'), 'utf-8')).decode('utf-8')

        batch = self.Batch.create({
            'name': 'دفعة التكرار الحتمي',
            'region_id': self.region.id,
            'date_range_id': period.id,
            'data_file': json_b64,
            'state': 'uploaded',
        })

        # التأكيد الأول
        batch.action_confirm()
        cmd_key = f"READING-BATCH:{batch.batch_uuid}"
        cmd1 = self.env['utility.workflow.command'].search([('idempotency_key', '=', cmd_key)], limit=1)
        self.assertTrue(cmd1)
        self.assertEqual(cmd1.state, 'executed')

        # النقر المزدوج على التأكيد مرة ثانية يرجع النتيجة السابقة من الكاش الحتمي دون تكرار التنفيذ
        batch.action_confirm()
        cmds = self.env['utility.workflow.command'].search([('idempotency_key', '=', cmd_key)])
        self.assertEqual(len(cmds), 1)

        # زر إعادة المحاولة الصريحة ينشئ أمر retry مستقل بزائدة RETRY:1
        batch.write({'state': 'partial'})
        batch.action_reset_to_uploaded()
        self.assertEqual(batch.retry_count, 1)

        retry_key = f"READING-BATCH:{batch.batch_uuid}:RETRY:1"
        retry_cmd = self.env['utility.workflow.command'].search([('idempotency_key', '=', retry_key)], limit=1)
        self.assertTrue(retry_cmd)
        self.assertEqual(retry_cmd.state, 'executed')
