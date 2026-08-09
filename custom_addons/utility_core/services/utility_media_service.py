import base64
import hashlib
import io
import logging
from PIL import Image

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
_logger = logging.getLogger(__name__)


class UtilityMediaService(models.AbstractModel):
    _name = 'utility.media.service'
    _description = 'مخدم إدارة الوسائط والصور الرقمية (Central Media Service)'

    @api.model
    def get_media_adapter(self):
        """إرجاع محول تخزين الوسائط والصور (Filesystem أو S3)"""
        backend = self.env['ir.config_parameter'].sudo().get_param('utility.media_backend', 'filesystem')
        if backend == 'filesystem':
            from ..adapters.media.filesystem import FilesystemMediaAdapter
            return FilesystemMediaAdapter(self.env)
        elif backend == 's3':
            from ..adapters.media.s3 import S3MediaAdapter
            if not getattr(S3MediaAdapter, 'PRODUCTION_READY', False):
                raise UserError(_("محول S3 Storage غير متاح. يرجى تفعيل التخزين المحلي."))
            return S3MediaAdapter(self.env)
        else:
            raise UserError(_("نوع محول تخزين الوسائط غير معروف: %s") % backend)

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
    def _detect_mime_from_bytes(self, raw_bytes):
        """اكتشاف نوع MIME الحقيقي من بصمة البايتات الأولية للصورة"""
        format_to_mime = {
            'JPEG': 'image/jpeg',
            'PNG': 'image/png',
            'WEBP': 'image/webp',
            'GIF': 'image/gif',
            'BMP': 'image/bmp',
            'TIFF': 'image/tiff',
        }
        try:
            image = Image.open(io.BytesIO(raw_bytes))
            fmt = image.format or 'JPEG'
            image.close()
            return format_to_mime.get(fmt, 'image/jpeg')
        except Exception:
            return 'image/jpeg'

    @api.model
    def store_media(
        self,
        file_data,
        filename,
        mimetype='image/jpeg',
        reading_id=False,
        batch_id=False,
        asset_type='meter_reading',
        reading_uuid=False,
    ):
        """تخزين وسائط جديدة ومعالجتها عبر Adapter وتوليد النسخ.

        العقد: file_data يجب أن يكون raw bytes (صورة ثنائية حقيقية).
        أي ناقل (UI / REST / AMI) مسؤول عن فك Base64 قبل الاستدعاء.
        """
        if not file_data:
            raise ValidationError(_("بيانات الصورة أو الملف فارغة."))

        if isinstance(file_data, str):
            raise ValidationError(_(
                "Media service لا يقبل Base64 strings. "
                "يجب فك الترميز إلى raw bytes قبل الاستدعاء."
            ))

        raw_bytes = bytes(file_data)

        try:
            img = Image.open(io.BytesIO(raw_bytes))
            img.verify()
        except Exception as exc:
            raise ValidationError(_(
                "بيانات الصورة غير صالحة — لا يمكن فتحها كصورة: %s"
            ) % filename) from exc

        mimetype = self._detect_mime_from_bytes(raw_bytes)

        sha256_hash = self.calculate_sha256(raw_bytes)
        file_size = len(raw_bytes)

        # فحص وجود أصل سابق بنفس البصمة لإعادة استخدام التخزين الثنائي دون تكرار الملف
        existing_asset = self.env['utility.media.asset'].sudo().search([
            ('sha256', '=', sha256_hash),
            ('file_size', '=', file_size),
            ('state', '=', 'ready'),
        ], limit=1)

        active_backend = self.env['ir.config_parameter'].sudo().get_param('utility.media_backend', 'filesystem')

        if existing_asset and existing_asset.original_path:
            _logger.info("Reusing binary media from SHA256 match asset %s for new evidence record", existing_asset.asset_uuid)
            new_asset = self.env['utility.media.asset'].sudo().create({
                'original_filename': filename,
                'mime_type': mimetype,
                'file_size': file_size,
                'sha256': sha256_hash,
                'asset_type': asset_type,
                'reading_id': reading_id,
                'reading_uuid': reading_uuid,
                'batch_id': batch_id,
                'state': 'ready',
                'storage_backend': existing_asset.storage_backend or active_backend,
                'original_path': existing_asset.original_path,
                'review_path': existing_asset.review_path or existing_asset.original_path,
                'thumbnail_path': existing_asset.thumbnail_path or existing_asset.original_path,
                'processed_at': fields.Datetime.now(),
            })
            return new_asset

        # إنشاء سجل الأصل الرقمي
        asset = self.env['utility.media.asset'].sudo().create({
            'original_filename': filename,
            'mime_type': mimetype,
            'file_size': file_size,
            'sha256': sha256_hash,
            'asset_type': asset_type,
            'reading_id': reading_id,
            'reading_uuid': reading_uuid,
            'batch_id': batch_id,
            'state': 'processing',
            'storage_backend': active_backend,
        })

        try:
            adapter = self.get_media_adapter()
            variants = self.generate_image_variants(raw_bytes)

            # تخزين النسخة الأصلية
            orig_ref = adapter.store(
                file_data=variants['original'],
                filename=f"orig_{filename}",
                mimetype=mimetype,
                metadata=self._media_storage_metadata(asset, 'original')
            )

            # تخزين نسخة المعاينة المكبرة
            rev_ref = adapter.store(
                file_data=variants['review'],
                filename=f"rev_{filename}",
                mimetype=mimetype,
                metadata=self._media_storage_metadata(asset, 'review')
            )

            # تخزين النسخة المصغرة
            thumb_ref = adapter.store(
                file_data=variants['thumbnail'],
                filename=f"thumb_{filename}",
                mimetype=mimetype,
                metadata=self._media_storage_metadata(asset, 'thumbnail')
            )

            refs = self._normalize_storage_refs(orig_ref, rev_ref, thumb_ref)
            asset.write({
                **refs,
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
    def _media_storage_metadata(self, asset, variant):
        batch = asset.batch_id
        period = batch.date_range_id if batch and hasattr(batch, 'date_range_id') else False
        return {
            'res_model': 'utility.media.asset',
            'res_id': asset.id,
            'asset_uuid': asset.asset_uuid,
            'batch_uuid': batch.batch_uuid if batch and hasattr(batch, 'batch_uuid') else asset.asset_uuid,
            'period_code': (
                getattr(period, 'period_code', False)
                or getattr(period, 'code', False)
                or getattr(period, 'name', False)
                or 'period_unknown'
            ),
            'variant': variant,
        }

    @api.model
    def _normalize_storage_refs(self, original_ref, review_ref, thumbnail_ref):
        return {
            'original_path': original_ref,
            'review_path': review_ref or original_ref,
            'thumbnail_path': thumbnail_ref or original_ref,
        }

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
