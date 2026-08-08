import base64
import logging
from odoo import http, _
from odoo.http import request, Response
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class UtilityMediaController(http.Controller):

    @http.route([
        '/utility/media/<string:asset_uuid>/<string:variant>',
        '/utility/media/<string:asset_uuid>',
    ], type='http', auth='public', methods=['GET'], csrf=False)
    def stream_media_variant(self, asset_uuid, variant='thumbnail', **kwargs):
        """
        بث الوسائط الرقمية ومقاطع المعاينة بأمان وتدقيق صلاحيات الوصول:
        - التحقق من تسجيل دخول المستخدم والنطاق الجغرافي.
        - تقديم نسخ الصورة (thumbnail, review, original).
        - دعم التخزين المؤقت في المتصفح عبر ETag و Max-Age.
        """
        if variant not in ['thumbnail', 'review', 'original']:
            variant = 'thumbnail'

        if not request.session.uid:
            return Response("Unauthorized", status=401)

        Asset = request.env['utility.media.asset'].sudo()
        asset = Asset.search([('asset_uuid', '=', asset_uuid)], limit=1)

        if not asset:
            return Response("Media asset not found", status=404)

        # 1. التحقق من صلاحيات الوصول والجغرافيا
        try:
            asset.check_user_access_security(request.env.user)
        except AccessError as e:
            _logger.warning("Unauthorized media access attempt for asset %s by user %s", asset_uuid, request.env.user.id)
            return Response("Access Denied", status=403)

        # 2. إعداد ترويسات التخزين المؤقت وحماية الأداء قبل أي استرجاع ثنائي
        etag = f'"{asset.asset_uuid}-{variant}-v{asset.revision}"'
        if request.httprequest.headers.get('If-None-Match') == etag:
            return Response(status=304)

        # 3. استرجاع البيانات الثنائية عبر Media Service
        media_service = request.env['utility.media.service'].sudo()
        raw_bytes = media_service.retrieve_media(asset, variant=variant)

        if not raw_bytes:
            # Fallback to ir.attachment if raw bytes empty from media service
            attachment = getattr(asset, f"{variant}_attachment_id", False) or asset.original_attachment_id
            if attachment and attachment.datas:
                raw_bytes = base64.b64decode(attachment.datas)

        if not raw_bytes:
            return Response("Media content unavailable", status=404)

        headers = [
            ('Content-Type', asset.mime_type or 'image/jpeg'),
            ('Content-Length', len(raw_bytes)),
            ('Cache-Control', 'private, max-age=86400'),
            ('ETag', etag),
        ]
        return request.make_response(raw_bytes, headers=headers)
