import base64
import json
import logging

from odoo import fields, http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class UtilityReaderAPI(http.Controller):
    """REST API لتطبيق القارئ (Flutter) — رفع القراءات والصور على شكل دفعات"""

    def _json_response(self, payload, status=200):
        return Response(
            json.dumps(payload, ensure_ascii=False),
            status=status,
            mimetype='application/json',
        )

    def _max_image_bytes(self):
        max_size_kb = int(request.env['ir.config_parameter'].sudo().get_param(
            'utility.max_image_size_kb', 80))
        return max_size_kb, max_size_kb * 1024

    def _get_owned_batch(self, batch_id):
        try:
            batch_id = int(batch_id)
        except (TypeError, ValueError):
            return request.env['utility.reading.batch']
        return request.env['utility.reading.batch'].search([
            ('id', '=', batch_id),
            ('user_id', '=', request.env.uid),
        ], limit=1)

    def _get_owned_batch_by_ref(self, batch_id=None, batch_uuid=None):
        if batch_id:
            return self._get_owned_batch(batch_id)
        if not batch_uuid:
            return request.env['utility.reading.batch']
        return request.env['utility.reading.batch'].search([
            ('batch_uuid', '=', batch_uuid),
            ('user_id', '=', request.env.uid),
        ], limit=1)
    # ================================================================
    # الخطوة 1: إنشاء سجل الدفعة
    # ================================================================
    @http.route('/api/v1/utility/reading/batch/create', type='json',
                auth='user', methods=['POST'])
    def create_batch(self, **kwargs):
        """
        إنشاء دفعة رفع قراءات جديدة.
        يجب تمرير:
          - date_range_id: معرف الفترة (إلزامي)
          - region_id: معرف المنطقة (اختياري)
          - total_readings: عدد القراءات في الدفعة (اختياري — يُحسب من الـ JSON لاحقاً)
        """
        params = request.jsonrequest
        date_range_id = params.get('date_range_id')
        if not date_range_id:
            return {'success': False, 'error': 'date_range_id is required'}

        # التحقق من وجود الفترة
        period = request.env['date.range'].browse(int(date_range_id))
        if not period.exists():
            return {'success': False, 'error': 'الفترة غير موجودة'}

        batch = request.env['utility.reading.batch'].create({
            'date_range_id': int(date_range_id),
            'region_id': int(params.get('region_id')) if params.get('region_id') else False,
            'total_readings': int(params.get('total_readings', 0)),
        })
        return {
            'success': True,
            'batch_id': batch.id,
            'batch_name': batch.name,
        }

    # ================================================================
    # الخطوة 2: رفع ملف JSON (البيانات فقط — بدون صور)
    # ================================================================
    @http.route('/api/v1/utility/reading/batch/upload_data', type='json',
                auth='user', methods=['POST'])
    def upload_batch_data(self, **kwargs):
        """
        رفع بيانات القراءات كملف JSON.
        يجب تمرير:
          - batch_id: معرف الدفعة (إلزامي)
          - data: محتوى JSON كـ dict أو string (إلزامي)
        """
        params = request.jsonrequest
        batch_id = params.get('batch_id')
        data = params.get('data')
        if not batch_id or not data:
            return {'success': False, 'error': 'batch_id and data are required'}

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return {'success': False, 'error': 'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي'}
        if batch.state != 'uploaded':
            return {'success': False, 'error': 'لا يمكن تعديل دفعة تمت معالجتها'}

        # تحويل البيانات إلى JSON string ثم Base64
        if isinstance(data, dict):
            json_str = json.dumps(data, ensure_ascii=False)
        elif isinstance(data, str):
            json_str = data
        else:
            return {'success': False, 'error': 'data must be dict or string'}

        encoded = base64.b64encode(json_str.encode('utf-8'))

        # حساب عدد القراءات من المحتوى
        try:
            parsed = json.loads(json_str) if isinstance(data, str) else data
            readings_list = parsed.get('readings', [])
            total = len(readings_list)
        except Exception:
            total = 0

        batch.write({
            'data_file': encoded,
            'data_filename': f'{batch.name}.json',
            'total_readings': total or batch.total_readings,
        })

        return {
            'success': True,
            'batch_id': batch.id,
            'total_readings': batch.total_readings,
        }

    # ================================================================
    # الخطوة 3: رفع صورة واحدة (كمرفق مرتبط بالدفعة)
    # ================================================================
    @http.route('/api/v1/utility/reading/batch/upload_image', type='json',
                auth='user', methods=['POST'])
    def upload_batch_image(self, **kwargs):
        """
        رفع صورة عداد واحدة كمرفق مرتبط بالدفعة.
        يجب تمرير:
          - batch_id: معرف الدفعة (إلزامي)
          - filename: اسم الملف مثل MTR-001234_20260701.jpg (إلزامي)
          - image: محتوى الصورة بصيغة Base64 (إلزامي)
        """
        params = request.jsonrequest
        batch_id = params.get('batch_id')
        filename = params.get('filename')
        image_data = params.get('image')

        if not batch_id or not filename or not image_data:
            return {'success': False, 'error': 'batch_id, filename, and image are required'}

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return {'success': False, 'error': 'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي'}
        if batch.state != 'uploaded':
            return {'success': False, 'error': 'لا يمكن تعديل دفعة تمت معالجتها'}

        media_backend = request.env['ir.config_parameter'].sudo().get_param(
            'utility.media_backend', 'filesystem')
        allow_legacy = str(request.env['ir.config_parameter'].sudo().get_param(
            'utility.allow_legacy_base64_upload', 'false')).lower() in ('1', 'true', 'yes')
        if media_backend != 'attachment' and not allow_legacy:
            return {
                'success': False,
                'error': 'Base64 image upload is disabled for production media storage. Use multipart upload_image_multipart.',
            }

        max_size, max_size_bytes = self._max_image_bytes()
        try:
            decoded = base64.b64decode(image_data)
            if len(decoded) > max_size_bytes:
                return {
                    'success': False,
                    'error': f'حجم الصورة ({len(decoded) / 1024:.0f} KB) يتجاوز الحد الأقصى ({max_size} KB)',
                }
        except Exception as e:
            return {'success': False, 'error': f'بيانات الصورة غير صالحة: {e}'}

        media_asset = request.env['utility.media.service'].sudo().store_media(
            file_data=decoded,
            filename=filename,
            mimetype='image/jpeg',
            batch_id=batch.id,
            asset_type='meter_reading'
        )

        return {
            'success': True,
            'asset_uuid': media_asset.asset_uuid,
            'attachment_id': media_asset.original_attachment_id.id if media_asset.original_attachment_id else False,
            'filename': filename,
        }

    @http.route('/api/v1/utility/reading/batch/upload_image_multipart', type='http',
                auth='user', methods=['POST'], csrf=False)
    def upload_batch_image_multipart(self, **kwargs):
        """
        Production image upload endpoint for Flutter.

        Multipart form fields:
          - batch_id or batch_uuid
          - file/image/photo: binary image file
          - filename: optional explicit filename
          - reading_uuid/client_reading_uuid: optional client-side reading reference
        """
        form = request.httprequest.form
        files = request.httprequest.files
        batch = self._get_owned_batch_by_ref(
            batch_id=form.get('batch_id') or kwargs.get('batch_id'),
            batch_uuid=form.get('batch_uuid') or kwargs.get('batch_uuid'),
        )
        if not batch.exists():
            return self._json_response({
                'success': False,
                'error': 'Batch not found or not owned by current user',
            }, status=404)
        if batch.state != 'uploaded':
            return self._json_response({
                'success': False,
                'error': 'Cannot upload media to a batch after processing has started',
            }, status=409)

        upload = files.get('file') or files.get('image') or files.get('photo')
        if not upload:
            return self._json_response({
                'success': False,
                'error': 'Multipart file field is required: file, image, or photo',
            }, status=400)

        filename = form.get('filename') or upload.filename or 'meter_reading.jpg'
        raw = upload.read()
        if not raw:
            return self._json_response({
                'success': False,
                'error': 'Uploaded image file is empty',
            }, status=400)
        max_size, max_size_bytes = self._max_image_bytes()
        if len(raw) > max_size_bytes:
            return self._json_response({
                'success': False,
                'error': f'Image size ({len(raw) / 1024:.0f} KB) exceeds max limit ({max_size} KB)',
            }, status=413)

        try:
            media_asset = request.env['utility.media.service'].sudo().store_media(
                file_data=raw,
                filename=filename,
                mimetype=upload.mimetype or 'image/jpeg',
                batch_id=batch.id,
                asset_type='meter_reading',
            )
            client_reading_uuid = form.get('reading_uuid') or form.get('client_reading_uuid') or False
            if client_reading_uuid:
                media_asset.write({'client_reading_uuid': client_reading_uuid})
        except Exception as exc:
            _logger.exception("Multipart image upload failed for batch %s", batch.id)
            return self._json_response({
                'success': False,
                'error': str(exc),
            }, status=400)

        return self._json_response({
            'success': True,
            'batch_id': batch.id,
            'batch_uuid': batch.batch_uuid,
            'asset_uuid': media_asset.asset_uuid,
            'reading_uuid': media_asset.client_reading_uuid or False,
            'filename': filename,
            'mime_type': media_asset.mime_type,
            'file_size': media_asset.file_size,
            'sha256': media_asset.sha256,
            'state': media_asset.state,
            'storage_backend': media_asset.storage_backend,
            'original_reference': media_asset.external_original_reference,
            'review_reference': media_asset.external_review_reference,
            'thumbnail_reference': media_asset.external_thumbnail_reference,
            'original_url': media_asset.original_url,
            'review_url': media_asset.review_url,
            'thumbnail_url': media_asset.thumbnail_url,
        })

    # ================================================================
    # الخطوة 4: تأكيد اكتمال الرفع — بدء المعالجة
    # ================================================================
    @http.route('/api/v1/utility/reading/batch/confirm', type='json',
                auth='user', methods=['POST'])
    def confirm_batch(self, **kwargs):
        """
        تأكيد اكتمال رفع الدفعة لبدء المعالجة بواسطة الـ Cron.
        يجب تمرير:
          - batch_id: معرف الدفعة (إلزامي)
        """
        params = request.jsonrequest
        batch_id = params.get('batch_id')
        if not batch_id:
            return {'success': False, 'error': 'batch_id is required'}

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return {'success': False, 'error': 'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي'}

        try:
            batch.action_confirm()
            return {
                'success': True,
                'batch_id': batch.id,
                'batch_name': batch.name,
                'state': batch.state,
                'total_readings': batch.total_readings,
                'total_images': request.env['utility.media.asset'].sudo().search_count([
                    ('batch_id', '=', batch.id),
                    ('asset_type', '=', 'meter_reading'),
                ]) or len(batch.image_ids),
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ================================================================
    # استعلام: حالة الدفعة (Polling)
    # ================================================================
    @http.route('/api/v1/utility/reading/batch/status', type='json',
                auth='user', methods=['POST'])
    def batch_status(self, **kwargs):
        """
        استعلام عن حالة دفعة محددة (يستخدمه التطبيق للـ polling).
        يجب تمرير:
          - batch_id: معرف الدفعة (إلزامي)
        """
        params = request.jsonrequest
        batch_id = params.get('batch_id')
        if not batch_id:
            return {'success': False, 'error': 'batch_id is required'}

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return {'success': False, 'error': 'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي'}

        return {
            'success': True,
            'batch_id': batch.id,
            'batch_name': batch.name,
            'state': batch.state,
            'total_readings': batch.total_readings,
            'processed_count': batch.processed_count,
            'error_count': batch.error_count,
            'media_asset_count': request.env['utility.media.asset'].sudo().search_count([
                ('batch_id', '=', batch.id),
                ('asset_type', '=', 'meter_reading'),
            ]),
            'error_log': batch.error_log or '',
        }

    # ================================================================
    # استعلام: الفترات المتاحة
    # ================================================================
    @http.route('/api/v1/utility/reading/periods', type='json',
                auth='user', methods=['POST'])
    def get_periods(self, **kwargs):
        """
        جلب الفترات (الأشهر) المتاحة لربط القراءات بها.
        """
        periods = request.env['date.range'].search([
            ('type_id.billing_period', '=', True),
        ], order='date_start desc', limit=12)

        return {
            'success': True,
            'periods': [{
                'id': p.id,
                'name': p.name,
                'date_start': p.date_start.isoformat() if p.date_start else None,
                'date_end': p.date_end.isoformat() if p.date_end else None,
                'is_current': p.is_current_period,
            } for p in periods],
        }

    # ================================================================
    # استعلام: بحث عن عداد (للتطبيق)
    # ================================================================
    @http.route('/api/v1/utility/reading/meter/lookup', type='json',
                auth='user', methods=['POST'])
    def meter_lookup(self, **kwargs):
        """
        بحث عن عداد بالرقم — يستخدمه التطبيق للتحقق أثناء الإدخال.
        يجب تمرير:
          - meter_number: رقم العداد (إلزامي)
        """
        params = request.jsonrequest
        meter_number = params.get('meter_number')
        if not meter_number:
            return {'success': False, 'error': 'meter_number is required'}

        meter = request.env['utility.meter'].search([
            ('meter_number', '=', meter_number)
        ], limit=1)

        if not meter:
            return {'success': False, 'error': 'العداد غير موجود'}

        customer = meter.customer_id
        return {
            'success': True,
            'meter': {
                'id': meter.id,
                'meter_number': meter.meter_number,
                'meter_type': meter.meter_type if hasattr(meter, 'meter_type') else None,
                'customer_id': customer.id if customer else None,
                'customer_name': customer.name if customer else None,
                'customer_number': customer.customer_number if customer else None,
                'address': customer.address if customer and hasattr(customer, 'address') else None,
            },
        }

    # ================================================================
    # استعلام: دفعات الجابي الحالي
    # ================================================================
    @http.route('/api/v1/utility/reading/batch/my', type='json',
                auth='user', methods=['POST'])
    def my_batches(self, **kwargs):
        """
        جلب دفعات الجابي الحالي (آخر 20 دفعة).
        """
        params = request.jsonrequest
        limit = params.get('limit', 20)

        batches = request.env['utility.reading.batch'].search([
            ('user_id', '=', request.env.uid),
        ], order='upload_date desc', limit=limit)

        return {
            'success': True,
            'batches': [{
                'id': b.id,
                'name': b.name,
                'upload_date': b.upload_date.isoformat() if b.upload_date else None,
                'period': b.date_range_id.name if b.date_range_id else None,
                'total_readings': b.total_readings,
                'processed_count': b.processed_count,
                'error_count': b.error_count,
                'state': b.state,
            } for b in batches],
        }
