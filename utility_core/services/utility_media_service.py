import base64
import hashlib
import io
import logging
from PIL import Image

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from ..adapters.media.attachment import AttachmentMediaAdapter

_logger = logging.getLogger(__name__)


class UtilityMediaService(models.AbstractModel):
    _name = 'utility.media.service'
    _description = 'مخدم إدارة الوسائط والصور الرقمية (Central Media Service)'

    @api.model
    def get_media_adapter(self):
        backend = self.env['ir.config_parameter'].sudo().get_param('utility.media_backend', 'attachment')
        if backend == 'attachment':
            return AttachmentMediaAdapter(self.env)
        else:
            # افتراضي للاستقرار أثناء التطوير
            return AttachmentMediaAdapter(self.env)

    @api.model
    def calculate_sha256(self, raw_bytes):
        return hashlib.sha256(raw_bytes).hexdigest() if raw_bytes else ''

    @api.model
    def generate_image_variants(self, raw_bytes):
        """توليد 3 نسخ محددة للأصل: الأصلية الكاملة، المعاينة المكبرة (1024px)، والمصغرة (150px)"""
        if not raw_bytes:
            return {'original': b'', 'review': b'', 'thumbnail': b''}

        try:
            image = Image.open(io.BytesIO(raw_bytes))
            image_format = image.format or 'JPEG'
            
            # 1. النسخة الأصلية
            original_bytes = raw_bytes

            # 2. نسخة المعاينة المكبرة (Review 1024px)
            review_img = image.copy()
            review_img.thumbnail((1024, 1024), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS)
            review_io = io.BytesIO()
            review_img.save(review_io, format=image_format, quality=85)
            review_bytes = review_io.getvalue()

            # 3. النسخة المصغرة (Thumbnail 150px)
            thumb_img = image.copy()
            thumb_img.thumbnail((150, 150), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS)
            thumb_io = io.BytesIO()
            thumb_img.save(thumb_io, format=image_format, quality=75)
            thumb_bytes = thumb_io.getvalue()

            return {
                'original': original_bytes,
                'review': review_bytes,
                'thumbnail': thumb_bytes,
            }
        except Exception as e:
            _logger.warning("Could not generate image variants (fallback to raw bytes): %s", str(e))
            return {
                'original': raw_bytes,
                'review': raw_bytes,
                'thumbnail': raw_bytes,
            }

    @api.model
    def store_media(self, file_data, filename, mimetype='image/jpeg', reading_id=False, batch_id=False, asset_type='meter_reading'):
        """تخزين وسائط جديدة ومعالجتها عبر Adapter وتوليد النسخ"""
        if not file_data:
            raise ValidationError(_("بيانات الصورة أو الملف فارغة."))

        if isinstance(file_data, str):
            raw_bytes = base64.b64decode(file_data)
        else:
            raw_bytes = file_data

        sha256_hash = self.calculate_sha256(raw_bytes)
        file_size = len(raw_bytes)

        # فحص إمكانية وجود أصل مطابق بالبصمة (منع تكرار التخزين الثنائي)
        existing_asset = self.env['utility.media.asset'].sudo().search([
            ('sha256', '=', sha256_hash),
            ('file_size', '=', file_size),
            ('state', '=', 'ready'),
        ], limit=1)

        if existing_asset:
            _logger.info("Reusing existing media asset %s (SHA256 match)", existing_asset.asset_uuid)
            if reading_id and not existing_asset.reading_id:
                existing_asset.write({'reading_id': reading_id})
            if batch_id and not existing_asset.batch_id:
                existing_asset.write({'batch_id': batch_id})
            return existing_asset

        # إنشاء سجل الأصل الرقمي
        asset = self.env['utility.media.asset'].sudo().create({
            'original_filename': filename,
            'mime_type': mimetype,
            'file_size': file_size,
            'sha256': sha256_hash,
            'asset_type': asset_type,
            'reading_id': reading_id,
            'batch_id': batch_id,
            'state': 'processing',
            'storage_backend': 'attachment',
        })

        try:
            adapter = self.get_media_adapter()
            variants = self.generate_image_variants(raw_bytes)

            # تخزين النسخة الأصلية
            orig_att = adapter.store(
                file_data=variants['original'],
                filename=f"orig_{filename}",
                mimetype=mimetype,
                metadata={'res_model': 'utility.media.asset', 'res_id': asset.id}
            )

            # تخزين نسخة المعاينة المكبرة
            rev_att = adapter.store(
                file_data=variants['review'],
                filename=f"rev_{filename}",
                mimetype=mimetype,
                metadata={'res_model': 'utility.media.asset', 'res_id': asset.id}
            )

            # تخزين النسخة المصغرة
            thumb_att = adapter.store(
                file_data=variants['thumbnail'],
                filename=f"thumb_{filename}",
                mimetype=mimetype,
                metadata={'res_model': 'utility.media.asset', 'res_id': asset.id}
            )

            asset.write({
                'original_attachment_id': orig_att.id,
                'review_attachment_id': rev_att.id,
                'thumbnail_attachment_id': thumb_att.id,
                'state': 'ready',
                'processed_at': fields.Datetime.now(),
            })
            return asset
        except Exception as e:
            asset.write({
                'state': 'failed',
                'error_code': 'STORAGE_ERROR',
                'error_message': str(e),
            })
            _logger.error("Failed to store media asset %s: %s", asset.asset_uuid, str(e))
            raise

    @api.model
    def retrieve_media(self, asset, variant='original'):
        if not asset or not asset.exists():
            return b''
        adapter = self.get_media_adapter()
        return adapter.retrieve(asset, variant=variant)

    @api.model
    def get_media_url(self, asset, variant='original'):
        if not asset or not asset.exists():
            return ''
        return asset.get_variant_url(variant=variant)
