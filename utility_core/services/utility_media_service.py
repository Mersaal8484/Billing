import hashlib
import io
import logging
from PIL import Image, UnidentifiedImageError

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from ..adapters.media.attachment import AttachmentMediaAdapter
from ..adapters.media.filesystem import FilesystemMediaAdapter
from ..adapters.media.s3 import S3MediaAdapter

_logger = logging.getLogger(__name__)


class UtilityMediaService(models.AbstractModel):
    _name = 'utility.media.service'
    _description = 'مخدم إدارة الوسائط والصور الرقمية (Central Media Service)'

    @api.model
    def get_media_adapter(self):
        """إرجاع المحول الخاص بتخزين الوسائط والصور الرقمية دون silent fallback"""
        backend = self.env['ir.config_parameter'].sudo().get_param('utility.media_backend', 'attachment')
        adapters = {
            'attachment': AttachmentMediaAdapter,
            'filesystem': FilesystemMediaAdapter,
            's3': S3MediaAdapter,
        }
        adapter_class = adapters.get(backend)
        if not adapter_class:
            raise UserError(_("نوع محول تخزين الوسائط غير معروف: %s") % backend)
        if backend == 's3' and not getattr(adapter_class, 'PRODUCTION_READY', False):
            raise UserError(_("محول S3 Storage غير جاهز للإنتاج حالياً (Placeholder Contract). يُرجى استخدام Odoo Attachments أو Local Filesystem."))
        return adapter_class(self.env)

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
        except (OSError, ValueError, KeyError) as exc:
            raise ValidationError(_("تعذر توليد نسخ الصورة من الملف المرفوع.")) from exc

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
            fmt = image.format
            image.close()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValidationError(_("تعذر اكتشاف نوع الصورة الحقيقي.")) from exc
        try:
            return format_to_mime[fmt]
        except KeyError as exc:
            raise ValidationError(_("صيغة الصورة غير مدعومة: %s") % fmt) from exc

    @api.model
    def store_media(self, file_data, filename, mimetype='image/jpeg', reading_id=False, batch_id=False, asset_type='meter_reading'):
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
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValidationError(_(
                "بيانات الصورة غير صالحة — لا يمكن فتحها كصورة: %s"
            ) % filename) from exc

        mimetype = self._detect_mime_from_bytes(raw_bytes)

        sha256_hash = self.calculate_sha256(raw_bytes)
        file_size = len(raw_bytes)
        active_backend = self.env['ir.config_parameter'].sudo().get_param('utility.media_backend', 'attachment')

        # فحص وجود أصل سابق بنفس البصمة لإعادة استخدام الـ Attachment الثنائي دون تكرار تخزين الملف
        existing_asset = self.env['utility.media.asset'].sudo().search([
            ('sha256', '=', sha256_hash),
            ('file_size', '=', file_size),
            ('state', '=', 'ready'),
        ], limit=1)

        create_vals = {
            'original_filename': filename,
            'mime_type': mimetype,
            'file_size': file_size,
            'sha256': sha256_hash,
            'asset_type': asset_type,
            'reading_id': reading_id,
            'state': 'processing',
            'storage_backend': active_backend,
        }
        if batch_id and 'batch_id' in self.env['utility.media.asset']._fields:
            create_vals['batch_id'] = batch_id

        if existing_asset and existing_asset.original_attachment_id:
            _logger.info("Reusing binary attachments from SHA256 match asset %s for new evidence record", existing_asset.asset_uuid)
            reused_vals = dict(create_vals, **{
                'state': 'ready',
                'storage_backend': existing_asset.storage_backend or active_backend,
                'original_attachment_id': existing_asset.original_attachment_id.id,
                'review_attachment_id': existing_asset.review_attachment_id.id if existing_asset.review_attachment_id else existing_asset.original_attachment_id.id,
                'thumbnail_attachment_id': existing_asset.thumbnail_attachment_id.id if existing_asset.thumbnail_attachment_id else existing_asset.original_attachment_id.id,
                'processed_at': fields.Datetime.now(),
            })
            new_asset = self.env['utility.media.asset'].sudo().create(reused_vals)
            return new_asset

        # إنشاء سجل الأصل الرقمي
        asset = self.env['utility.media.asset'].sudo().create(create_vals)

        try:
            adapter = self.get_media_adapter()
            variants = self.generate_image_variants(raw_bytes)

            # تخزين النسخة الأصلية
            orig_att = adapter.store(
                file_data=variants['original'],
                filename=f"orig_{filename}",
                mimetype=mimetype,
                metadata={'res_model': 'utility.media.asset', 'res_id': asset.id, 'asset_uuid': asset.asset_uuid}
            )

            # تخزين نسخة المعاينة المكبرة
            rev_att = adapter.store(
                file_data=variants['review'],
                filename=f"rev_{filename}",
                mimetype=mimetype,
                metadata={'res_model': 'utility.media.asset', 'res_id': asset.id, 'asset_uuid': asset.asset_uuid}
            )

            # تخزين النسخة المصغرة
            thumb_att = adapter.store(
                file_data=variants['thumbnail'],
                filename=f"thumb_{filename}",
                mimetype=mimetype,
                metadata={'res_model': 'utility.media.asset', 'res_id': asset.id, 'asset_uuid': asset.asset_uuid}
            )

            asset.write({
                'original_attachment_id': orig_att.id,
                'review_attachment_id': rev_att.id,
                'thumbnail_attachment_id': thumb_att.id,
                'state': 'ready',
                'processed_at': fields.Datetime.now(),
            })
            return asset
        except (AccessError, UserError, ValidationError, OSError) as exc:
            asset.write({
                'state': 'failed',
                'error_code': 'STORAGE_ERROR',
                'error_message': str(exc),
            })
            _logger.error("Failed to store media asset %s: %s", asset.asset_uuid, str(exc))
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
