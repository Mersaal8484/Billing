from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from ..adapters.workflow.local import LocalWorkflowAdapter
from ..adapters.workflow.temporal import TemporalWorkflowAdapter
from ..adapters.media.attachment import AttachmentMediaAdapter
from ..adapters.media.filesystem import FilesystemMediaAdapter
from ..adapters.media.s3 import S3MediaAdapter


class TestUtilityInfrastructureSettings(TransactionCase):

    def setUp(self):
        super().setUp()
        self.WorkflowService = self.env['utility.workflow.service']
        self.MediaService = self.env['utility.media.service']
        self.ConfigParam = self.env['ir.config_parameter'].sudo()

    def test_01_default_infrastructure_adapters(self):
        """1. اختبار الإعدادات الافتراضية للبنية التحتية (Local Workflow & Attachment Media)"""
        self.ConfigParam.set_param('utility.workflow_adapter', 'local')
        self.ConfigParam.set_param('utility.media_backend', 'attachment')

        wf_adapter = self.WorkflowService._get_workflow_adapter()
        self.assertIsInstance(wf_adapter, LocalWorkflowAdapter)

        media_adapter = self.MediaService.get_media_adapter()
        self.assertIsInstance(media_adapter, AttachmentMediaAdapter)

    def test_02_temporal_workflow_adapter_validation_and_no_silent_fallback(self):
        """2. اختبار فحص إعدادات Temporal ومنع silent fallback إلى Local"""
        self.ConfigParam.set_param('utility.workflow_adapter', 'temporal')
        self.ConfigParam.set_param('utility.temporal_target_host', '')

        # يجب أن يرفع UserError بدلاً من العودة إلى LocalWorkflowAdapter صمتاً
        with self.assertRaises(UserError):
            self.WorkflowService._get_workflow_adapter()

        # إدخال عنوان خادم Temporal
        self.ConfigParam.set_param('utility.temporal_target_host', 'localhost:7233')
        wf_adapter = self.WorkflowService._get_workflow_adapter()
        self.assertIsInstance(wf_adapter, TemporalWorkflowAdapter)

    def test_03_filesystem_media_adapter_validation(self):
        """3. اختبار فحص إعدادات التخزين على القرص Filesystem"""
        self.ConfigParam.set_param('utility.media_backend', 'filesystem')
        self.ConfigParam.set_param('utility.filesystem_storage_path', '')

        with self.assertRaises(UserError):
            self.MediaService.get_media_adapter()

        self.ConfigParam.set_param('utility.filesystem_storage_path', '/tmp/utility_media_test')
        media_adapter = self.MediaService.get_media_adapter()
        self.assertIsInstance(media_adapter, FilesystemMediaAdapter)

    def test_04_s3_media_adapter_validation(self):
        """4. اختبار فحص إعدادات التخزين السحابي S3"""
        self.ConfigParam.set_param('utility.media_backend', 's3')
        self.ConfigParam.set_param('utility.s3_endpoint_url', '')

        with self.assertRaises(UserError):
            self.MediaService.get_media_adapter()

        self.ConfigParam.set_param('utility.s3_endpoint_url', 'https://s3.example.com')
        self.ConfigParam.set_param('utility.s3_bucket_name', 'utility-bucket')
        self.ConfigParam.set_param('utility.s3_access_key', 'AKIAIOSFODNN7EXAMPLE')
        self.ConfigParam.set_param('utility.s3_secret_key', 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY')

        media_adapter = self.MediaService.get_media_adapter()
        self.assertIsInstance(media_adapter, S3MediaAdapter)

        # اختبار أسبقية متغيرات البيئة OS Environment Variables على إعدادات القاعدة
        import os
        os.environ['S3_ACCESS_KEY'] = 'ENV_ACCESS_KEY'
        os.environ['S3_SECRET_KEY'] = 'ENV_SECRET_KEY'
        env_adapter = S3MediaAdapter(self.env)
        self.assertEqual(env_adapter.access_key, 'ENV_ACCESS_KEY')
        self.assertEqual(env_adapter.secret_key, 'ENV_SECRET_KEY')
        del os.environ['S3_ACCESS_KEY']
        del os.environ['S3_SECRET_KEY']

    def test_05_res_config_settings_v1_stabilization_constraints(self):
        """5. اختبار قيود شاشة الإعدادات لمنع تفعيل الأنظمة التي في مرحلة Placeholder (Temporal / S3)"""
        settings = self.env['res.config.settings'].create({
            'workflow_backend': 'temporal',
            'temporal_target_host': 'localhost:7233',
        })
        with self.assertRaises(ValidationError):
            settings._check_infrastructure_backend_config()

        settings_s3 = self.env['res.config.settings'].create({
            'media_backend': 's3',
            's3_endpoint_url': 'https://s3.example.com',
            's3_bucket_name': 'test-bucket',
            's3_access_key': 'key',
            's3_secret_key': 'secret',
        })
        with self.assertRaises(ValidationError):
            settings_s3._check_infrastructure_backend_config()

    def test_06_filesystem_adapter_partitioning(self):
        """6. اختبار تقسيم مسار التخزين على القرص باستخدام UUID للأصل"""
        import os
        import tempfile
        test_dir = tempfile.mkdtemp()
        self.ConfigParam.set_param('utility.media_backend', 'filesystem')
        self.ConfigParam.set_param('utility.filesystem_storage_path', test_dir)

        adapter = self.MediaService.get_media_adapter()
        attachment = adapter.store(
            file_data=b'test binary data',
            filename='test_photo.jpg',
            mimetype='image/jpeg',
            metadata={'res_model': 'utility.media.asset', 'res_id': 99, 'asset_uuid': 'uuid-12345'}
        )
        self.assertTrue(attachment.url.startswith('file://'))
        expected_file_path = os.path.join(test_dir, 'uuid-12345', 'test_photo.jpg')
        self.assertEqual(attachment.url.replace('file://', ''), expected_file_path)
        self.assertTrue(os.path.exists(expected_file_path))

    def test_07_media_service_dynamic_storage_backend_metadata(self):
        """7. اختبار تعيين خيار التخزين ديناميكياً في السجل (storage_backend)"""
        self.ConfigParam.set_param('utility.media_backend', 'attachment')
        asset = self.MediaService.store_media(
            file_data=b'fake image data',
            filename='test_dynamic.jpg',
            mimetype='image/jpeg'
        )
        self.assertEqual(asset.storage_backend, 'attachment')
