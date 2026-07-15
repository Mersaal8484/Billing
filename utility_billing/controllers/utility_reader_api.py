import base64
import json
import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class UtilityReaderAPI(http.Controller):
    """REST API لتطبيق القارئ (Flutter) — رفع القراءات والصور على شكل دفعات"""

    def _get_owned_batch(self, batch_id):
        try:
            batch_id = int(batch_id)
        except (TypeError, ValueError):
            return request.env['utility.reading.batch']
        return request.env['utility.reading.batch'].search([
            ('id', '=', batch_id),
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

        # التحقق من حجم الصورة (الحد الأقصى 100 KB)
        max_size = int(request.env['ir.config_parameter'].sudo().get_param(
            'utility.max_image_size_kb', 100))
        try:
            decoded = base64.b64decode(image_data)
            size_kb = len(decoded) / 1024
            if size_kb > max_size:
                return {
                    'success': False,
                    'error': f'حجم الصورة ({size_kb:.0f} KB) يتجاوز الحد الأقصى ({max_size} KB)',
                }
        except Exception as e:
            return {'success': False, 'error': f'بيانات الصورة غير صالحة: {e}'}

        attachment = request.env['ir.attachment'].create({
            'name': filename,
            'datas': image_data,
            'res_model': 'utility.reading.batch',
            'res_id': batch.id,
            'mimetype': 'image/jpeg',
        })

        return {
            'success': True,
            'attachment_id': attachment.id,
            'filename': filename,
        }

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
                'total_images': len(batch.image_ids),
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
