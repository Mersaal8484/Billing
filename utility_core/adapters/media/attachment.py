import base64
import binascii
from odoo import _
from odoo.exceptions import ValidationError
from .base import AbstractMediaStorageAdapter


class AttachmentMediaAdapter(AbstractMediaStorageAdapter):
    """محول تخزين الوسائط الرقمية عبر مرفقات أودو الرسمية (ir.attachment) للتطوير والاختبار المحلي"""

    def __init__(self, env):
        self.env = env

    def store(self, *, file_data, filename, mimetype, metadata=None):
        if not file_data:
            raise ValidationError(_("محتوى الملف فارغ."))

        if isinstance(file_data, bytes):
            b64_data = base64.b64encode(file_data).decode('utf-8')
        else:
            b64_data = file_data

        vals = {
            'name': filename,
            'datas': b64_data,
            'mimetype': mimetype,
            'res_model': metadata.get('res_model', 'utility.media.asset') if metadata else 'utility.media.asset',
            'res_id': metadata.get('res_id', 0) if metadata else 0,
        }

        attachment = self.env['ir.attachment'].sudo().create(vals)
        return attachment

    def retrieve(self, asset, variant='original'):
        attachment = self._get_attachment_for_variant(asset, variant)
        if not attachment or not attachment.datas:
            return b''
        try:
            return base64.b64decode(attachment.datas, validate=True)
        except (binascii.Error, TypeError, ValueError):
            return b''

    def delete(self, asset):
        attachments = self.env['ir.attachment'].sudo()
        if asset.original_attachment_id:
            attachments |= asset.original_attachment_id
        if asset.review_attachment_id:
            attachments |= asset.review_attachment_id
        if asset.thumbnail_attachment_id:
            attachments |= asset.thumbnail_attachment_id
        if attachments:
            attachments.unlink()
        return True

    def exists(self, asset, variant='original'):
        attachment = self._get_attachment_for_variant(asset, variant)
        return bool(attachment and attachment.exists())

    def get_url(self, asset, variant='original'):
        attachment = self._get_attachment_for_variant(asset, variant)
        if not attachment:
            return ''
        return f"/web/image/{attachment.id}"
