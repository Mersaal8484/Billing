import os
import logging
import re
from datetime import date
from odoo import _
from odoo.tools import config
from odoo.exceptions import UserError, ValidationError
from .base import AbstractMediaStorageAdapter

_logger = logging.getLogger(__name__)


class FilesystemMediaAdapter(AbstractMediaStorageAdapter):
    """محول تخزين الوسائط والصور على نظام الملفات المشترك (Filesystem Media Adapter)"""

    def __init__(self, env):
        self.env = env
        self.storage_path = (
            env['ir.config_parameter'].sudo().get_param('utility.filesystem_storage_path', '')
            or os.path.join(config['data_dir'], 'utility-media')
        )
        
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

        metadata = metadata or {}
        today = date.today()
        variant = self._safe_segment(metadata.get('variant') or 'original')
        period = self._safe_segment(metadata.get('period_code') or 'period_unknown')
        batch = self._safe_segment(metadata.get('batch_uuid') or metadata.get('asset_uuid') or 'batch_unknown')
        safe_filename = self._safe_filename(filename)

        relative_dir = os.path.join(
            'readings',
            f'{today:%Y}',
            f'{today:%m}',
            period,
            batch,
            variant,
        )
        target_dir = os.path.join(self.storage_path, relative_dir)
        os.makedirs(target_dir, exist_ok=True)

        file_bytes = file_data if isinstance(file_data, bytes) else file_data.encode('utf-8')
        file_path = os.path.join(target_dir, safe_filename)
        temp_path = f'{file_path}.uploading'
        with open(temp_path, 'wb') as f:
            f.write(file_bytes)
        os.replace(temp_path, file_path)

        return os.path.join(relative_dir, safe_filename).replace(os.sep, '/')

    def retrieve(self, asset, variant='original'):
        reference = self._get_reference_for_variant(asset, variant)
        if not reference:
            return b''
        file_path = self._resolve_reference(reference)
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                return f.read()
        return b''

    def delete(self, asset):
        for reference in {
            asset.original_path,
            asset.review_path,
            asset.thumbnail_path,
        }:
            if not reference:
                continue
            file_path = self._resolve_reference(reference)
            if os.path.exists(file_path):
                os.remove(file_path)
        return True

    def exists(self, asset, variant='original'):
        reference = self._get_reference_for_variant(asset, variant)
        file_path = self._resolve_reference(reference) if reference else ''
        return os.path.exists(file_path)

    def get_url(self, asset, variant='original'):
        return self._get_reference_for_variant(asset, variant) or ''

    def _get_reference_for_variant(self, asset, variant):
        if variant == 'thumbnail' and asset.thumbnail_path:
            return asset.thumbnail_path
        if variant == 'review' and asset.review_path:
            return asset.review_path
        return asset.original_path

    def _resolve_reference(self, reference):
        storage_root = os.path.abspath(self.storage_path)
        file_path = os.path.abspath(os.path.join(storage_root, reference))
        if os.path.commonpath([storage_root, file_path]) != storage_root:
            raise ValidationError(_("مرجع ملف الوسائط خارج مسار التخزين المسموح."))
        return file_path

    def _safe_segment(self, value):
        value = str(value or '').strip()
        return re.sub(r'[^A-Za-z0-9_.-]+', '_', value)[:120] or 'unknown'

    def _safe_filename(self, filename):
        filename = os.path.basename(str(filename or '').strip())
        return re.sub(r'[^A-Za-z0-9_.-]+', '_', filename)[:180] or 'media.bin'
