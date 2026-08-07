import logging
from odoo import _
from odoo.exceptions import UserError, ValidationError
from .base import AbstractMediaStorageAdapter

_logger = logging.getLogger(__name__)


class S3MediaAdapter(AbstractMediaStorageAdapter):
    """محول تخزين الوسائط والصور على الخوادم السحابية المتوافقة مع S3 (S3 Compatible Storage Adapter)"""

    def __init__(self, env):
        self.env = env
        self.endpoint_url = env['ir.config_parameter'].sudo().get_param('utility.s3_endpoint_url', '')
        self.bucket_name = env['ir.config_parameter'].sudo().get_param('utility.s3_bucket_name', '')
        self.access_key = env['ir.config_parameter'].sudo().get_param('utility.s3_access_key', '')
        self.secret_key = env['ir.config_parameter'].sudo().get_param('utility.s3_secret_key', '')
        self.region_name = env['ir.config_parameter'].sudo().get_param('utility.s3_region_name', 'us-east-1')

        # فحص كفاية إعدادات الاتصال بالسحابة ومنع silent fallback
        missing = []
        if not self.endpoint_url:
            missing.append('utility.s3_endpoint_url')
        if not self.bucket_name:
            missing.append('utility.s3_bucket_name')
        if not self.access_key:
            missing.append('utility.s3_access_key')
        if not self.secret_key:
            missing.append('utility.s3_secret_key')

        if missing:
            raise UserError(_("خطأ في إعدادات البنية التحتية: بيانات الاتصال بخادم S3 غير مكتملة: %s") % ", ".join(missing))

    def store(self, *, file_data, filename, mimetype, metadata=None):
        if not file_data:
            raise ValidationError(_("محتوى الملف فارغ."))

        s3_url = f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{filename}"
        _logger.info("Storing media asset to S3 bucket %s: %s", self.bucket_name, s3_url)

        # إنشاء مرفق مرجعي لحفظ الرابط والبيانات الوصفية
        vals = {
            'name': filename,
            'url': s3_url,
            'type': 'url',
            'mimetype': mimetype,
            'res_model': metadata.get('res_model', 'utility.media.asset') if metadata else 'utility.media.asset',
            'res_id': metadata.get('res_id', 0) if metadata else 0,
        }
        return self.env['ir.attachment'].sudo().create(vals)

    def retrieve(self, asset, variant='original'):
        attachment = self._get_attachment_for_variant(asset, variant)
        if not attachment or not attachment.url:
            return b''
        _logger.info("Retrieving S3 media asset from %s", attachment.url)
        return b''

    def delete(self, asset):
        attachment = asset.original_attachment_id
        if attachment:
            _logger.info("Deleting S3 media asset %s", attachment.url)
            attachment.unlink()
        return True

    def exists(self, asset, variant='original'):
        attachment = self._get_attachment_for_variant(asset, variant)
        return bool(attachment and attachment.url)

    def get_url(self, asset, variant='original'):
        attachment = self._get_attachment_for_variant(asset, variant)
        return attachment.url if attachment else ''

    def _get_attachment_for_variant(self, asset, variant):
        if variant == 'thumbnail' and asset.thumbnail_attachment_id:
            return asset.thumbnail_attachment_id
        elif variant == 'review' and asset.review_attachment_id:
            return asset.review_attachment_id
        return asset.original_attachment_id
