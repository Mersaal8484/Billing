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
