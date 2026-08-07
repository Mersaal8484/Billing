import os
import logging
from odoo import _
from odoo.exceptions import UserError, ValidationError
from .base import AbstractMediaStorageAdapter

_logger = logging.getLogger(__name__)


class FilesystemMediaAdapter(AbstractMediaStorageAdapter):
    """محول تخزين الوسائط والصور على نظام الملفات المشترك (Filesystem Media Adapter)"""

    def __init__(self, env):
        self.env = env
        self.storage_path = env['ir.config_parameter'].sudo().get_param('utility.filesystem_storage_path', '')
        
        if not self.storage_path:
            raise UserError(_("خطأ في إعدادات البنية التحتية: مسار تخزين الملفات غير محدد (utility.filesystem_storage_path)."))
        
        if not os.path.exists(self.storage_path):
            try:
                os.makedirs(self.storage_path, exist_ok=True)
            except Exception as e:
                raise UserError(_("خطأ في إعدادات البنية التحتية: تعذر إنشاء مسار تخزين الملفات: %s") % str(e))

    def store(self, *, file_data, filename, mimetype, metadata=None):
        if not file_data:
            raise ValidationError(_("محتوى الملف فارغ."))

        sub_folder = metadata.get('asset_uuid') if metadata and metadata.get('asset_uuid') else (str(metadata.get('res_id')) if metadata and metadata.get('res_id') else 'shared')
        target_dir = os.path.join(self.storage_path, sub_folder)
        os.makedirs(target_dir, exist_ok=True)

        file_bytes = file_data if isinstance(file_data, bytes) else file_data.encode('utf-8')
        file_path = os.path.join(target_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(file_bytes)

        # إنشاء مرفق مرجعي لحفظ الرابط والبيانات الوصفية
        vals = {
            'name': filename,
            'url': f"file://{file_path}",
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
        file_path = attachment.url.replace('file://', '')
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                return f.read()
        return b''

    def delete(self, asset):
        attachment = asset.original_attachment_id
        if attachment and attachment.url:
            file_path = attachment.url.replace('file://', '')
            if os.path.exists(file_path):
                os.remove(file_path)
            attachment.unlink()
        return True

    def exists(self, asset, variant='original'):
        attachment = self._get_attachment_for_variant(asset, variant)
        if not attachment or not attachment.url:
            return False
        file_path = attachment.url.replace('file://', '')
        return os.path.exists(file_path)

    def get_url(self, asset, variant='original'):
        attachment = self._get_attachment_for_variant(asset, variant)
        return attachment.url if attachment else ''

    def _get_attachment_for_variant(self, asset, variant):
        if variant == 'thumbnail' and asset.thumbnail_attachment_id:
            return asset.thumbnail_attachment_id
        elif variant == 'review' and asset.review_attachment_id:
            return asset.review_attachment_id
        return asset.original_attachment_id
