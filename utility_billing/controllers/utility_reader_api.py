import base64
import binascii
import json
import logging

from odoo import fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class UtilityReaderAPI(http.Controller):
    """REST API لتطبيق القارئ (Flutter) — رفع القراءات والصور على شكل دفعات"""

    @staticmethod
    def _error(code, message):
        """Return the stable API error envelope without changing success payloads."""
        return {'success': False, 'code': code, 'error': message}

    def _resolve_meter_identifiers(self, params):
        """Resolve supplied meter identifiers and reject contradictory values."""
        Meter = request.env['utility.meter']
        identifiers = []
        if params.get('meter_id') not in (None, '', False):
            try:
                meter = Meter.search([('id', '=', int(params['meter_id']))], limit=1)
            except (TypeError, ValueError):
                meter = Meter.browse()
            identifiers.append(('meter_id', meter))
        for key in ('operational_number', 'meter_number'):
            value = params.get(key)
            if value not in (None, '', False):
                identifiers.append((key, Meter.search([(key, '=', str(value).strip())], limit=1)))
        if not identifiers:
            return Meter.browse(), 'IDENTIFIER_REQUIRED'
        if any(not meter for _, meter in identifiers):
            return Meter.browse(), 'METER_NOT_FOUND'
        meter_ids = {meter.id for _, meter in identifiers}
        if len(meter_ids) > 1:
            return Meter.browse(), 'METER_IDENTIFIER_MISMATCH'
        return identifiers[0][1], False

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
            return self._error('VALIDATION_ERROR', 'date_range_id is required')

        # التحقق من صحة المعرف والفترة والشركة قبل إنشاء الدفعة
        try:
            date_range_id = int(date_range_id)
        except (TypeError, ValueError):
            return self._error('VALIDATION_ERROR', 'date_range_id must be numeric')
        period = request.env['date.range'].browse(date_range_id)
        if (not period.exists() or period.period_role != 'reading'
                or period.state != 'open'
                or period.company_id not in (False, request.env.company)):
            return self._error('INVALID_READING_PERIOD', 'الفترة غير موجودة')

        region_id = params.get('region_id')
        if region_id:
            try:
                region_id = int(region_id)
            except (TypeError, ValueError):
                return self._error('VALIDATION_ERROR', 'region_id must be numeric')
            region = request.env['utility.region'].browse(region_id)
            if (not region.exists() or region.type != 'region'
                    or (period.region_ids and region not in period.region_ids)):
                return self._error('INVALID_REGION', 'المنطقة غير صالحة لهذه الفترة')

        total_readings_raw = params.get('total_readings', 0)
        try:
            total_readings = int(total_readings_raw)
            if total_readings < 0:
                raise ValueError()
        except (TypeError, ValueError):
            return self._error(
                'INVALID_TOTAL_READINGS',
                'total_readings must be a non-negative integer',
            )

        batch = request.env['utility.reading.batch'].create({
            'date_range_id': date_range_id,
            'region_id': region_id or False,
            'total_readings': total_readings,
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
        if not batch_id or data is None:
            return self._error('VALIDATION_ERROR', 'batch_id and data are required')

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return self._error('BATCH_NOT_FOUND', 'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي')
        if batch.state != 'uploaded':
            return self._error('BATCH_NOT_EDITABLE', 'لا يمكن تعديل دفعة تمت معالجتها')

        # تحويل البيانات وإثبات صحة الـ JSON قبل تنفيذ أي عملية كتابة
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                return self._error('INVALID_JSON', 'data must be valid JSON object')
            json_str = data
        elif isinstance(data, dict):
            parsed = data
            json_str = json.dumps(data, ensure_ascii=False)
        else:
            return self._error('INVALID_JSON', 'data must be dict or string')

        if not isinstance(parsed, dict):
            return self._error('INVALID_JSON', 'data must be valid JSON object')

        readings_list = parsed.get('readings')
        if readings_list is not None and not isinstance(readings_list, list):
            return self._error('INVALID_JSON', 'readings must be a list')

        encoded = base64.b64encode(json_str.encode('utf-8'))
        total = len(readings_list) if isinstance(readings_list, list) else 0

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
            return self._error(
                'VALIDATION_ERROR',
                'batch_id, filename, and image are required',
            )

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return self._error('BATCH_NOT_FOUND', 'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي')
        if batch.state != 'uploaded':
            return self._error('BATCH_NOT_EDITABLE', 'لا يمكن تعديل دفعة تمت معالجتها')

        # التحقق من حجم الصورة (الحد الأقصى 100 KB)
        max_size = int(request.env['ir.config_parameter'].sudo().get_param(
            'utility.max_image_size_kb', 100))
        try:
            decoded = base64.b64decode(image_data, validate=True)
            size_kb = len(decoded) / 1024
            if size_kb > max_size:
                return self._error(
                    'IMAGE_TOO_LARGE',
                    f'حجم الصورة ({size_kb:.0f} KB) يتجاوز الحد الأقصى ({max_size} KB)',
                )
        except (binascii.Error, TypeError, ValueError) as e:
            _logger.warning("Invalid base64 image data uploaded for batch %s: %s", batch_id, str(e))
            return self._error('INVALID_BASE64', 'بيانات الصورة غير صالحة (Base64 Decode Error)')

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
            return self._error('VALIDATION_ERROR', 'batch_id is required')

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return self._error('BATCH_NOT_FOUND', 'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي')

        try:
            with request.env.cr.savepoint():
                batch.action_confirm()
            return {
                'success': True,
                'batch_id': batch.id,
                'batch_name': batch.name,
                'state': batch.state,
                'total_readings': batch.total_readings,
                'total_images': len(batch.image_ids),
            }
        except (AccessError, UserError, ValidationError) as e:
            _logger.warning("Failed to confirm reading batch %s: %s", batch_id, str(e))
            return self._error('BUSINESS_RULE_ERROR', str(e))

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
            return self._error('VALIDATION_ERROR', 'batch_id is required')

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return self._error('BATCH_NOT_FOUND', 'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي')

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
            ('period_role', '=', 'reading'),
            ('state', '=', 'open'),
            '|', ('company_id', '=', False), ('company_id', '=', request.env.company.id)
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
          - meter_id أو operational_number أو meter_number: أحد معرفات العداد
        """
        params = request.jsonrequest
        meter, error_code = self._resolve_meter_identifiers(params)
        if error_code == 'IDENTIFIER_REQUIRED':
            return self._error(
                'VALIDATION_ERROR',
                'meter_id, operational_number or meter_number is required',
            )
        if error_code == 'METER_IDENTIFIER_MISMATCH':
            return self._error(error_code, 'المعرفات الممررة للعداد متعارضة')
        if error_code:
            return self._error(error_code, 'العداد غير موجود')

        customer = meter.customer_id
        return {
            'success': True,
            'meter': {
                'id': meter.id,
                'meter_number': meter.meter_number,
                'operational_number': meter.operational_number or None,
                'meter_type': meter.meter_type if hasattr(meter, 'meter_type') else None,
                'customer_id': customer.id if customer else None,
                'customer_name': customer.partner_id.name if customer and customer.partner_id else None,
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
        params = request.jsonrequest or {}
        limit_raw = params.get('limit', 20)
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            return self._error('INVALID_LIMIT', 'limit must be an integer')

        limit = max(1, min(limit, 100))

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

    # ================================================================
    # استعلام: صلاحيات المستخدم (Mobile App Dashboard)
    # ================================================================
    @http.route('/api/v1/utility/auth/roles', type='json',
                auth='user', methods=['POST', 'GET'])
    def auth_roles(self, **kwargs):
        """
        يرجع أدوار المستخدم الحالي (كاشف، محصل، مشرف) من خلال Security Groups في Odoo.
        """
        user = request.env.user
        return {
            'success': True,
            'uid': user.id,
            'name': user.name,
            'roles': {
                'is_meter_reader': user.has_group('utility_core.group_utility_meter_reader'),
                'is_collector': user.has_group('utility_core.group_utility_collector'),
                'is_supervisor': user.has_group('utility_core.group_utility_supervisor'),
            }
        }

    # ================================================================
    # استعلام: مشتركي الكاشف الحالي
    # ================================================================
    @http.route('/api/v1/utility/reader/subscribers', type='json',
                auth='user', methods=['POST', 'GET'])
    def reader_subscribers(self, **kwargs):
        """
        جلب قائمة المشتركين المخصصين للكاشف المسجل دخوله.
        يبحث عبر assigned_route_ids أو عبر سجل utility.meter.reader المرتبط.
        """
        user = request.env.user

        # البحث عبر سجل الكاشف المرتبط بالمستخدم
        route_ids = user.assigned_route_ids.ids
        meter_reader = request.env['utility.meter.reader'].sudo().search(
            [('user_id', '=', user.id)], limit=1
        )
        if meter_reader:
            route_ids = list(set(route_ids + meter_reader.route_ids.ids))

        if not route_ids:
            return {'success': True, 'subscribers': [], 'count': 0}

        customers = request.env['utility.customer'].sudo().search([
            ('route_id', 'in', route_ids)
        ])

        result = []
        for c in customers:
            meter = c.meter_id
            # استخدام عنوان الشريك المحاسبي إذا توفر لتجنب خطأ AttributeError
            address = c.partner_id.contact_address if c.partner_id and hasattr(c.partner_id, 'contact_address') else ''
            result.append({
                'id': c.id,
                'customer_number': c.customer_number,
                'name': c.partner_id.name if c.partner_id else '',
                'address': address or '',
                'route_id': c.route_id.id if c.route_id else None,
                'route_name': c.route_id.name if c.route_id else '',
                'meter_id': meter.id if meter else None,
                'meter_number': meter.meter_number if meter else '',
            })

        return {
            'success': True,
            'count': len(result),
            'subscribers': result,
        }

    # ================================================================
    # إجراء: رفع قراءة لعميل
    # ================================================================
    @http.route('/api/v1/utility/reader/reading/submit', type='json',
                auth='user', methods=['POST'])
    def submit_reading(self, **kwargs):
        """
        رفع قراءة فردية لعداد العميل من قبل الكاشف.
        """
        params = request.jsonrequest
        
        # Resolve meter
        meter, error_code = self._resolve_meter_identifiers(params)
        if error_code:
            return self._error(error_code or 'METER_NOT_FOUND', 'العداد غير موجود أو البيانات غير مكتملة')

        user = request.env.user
        
        # تحقق من ملكية المسار
        if meter.customer_id.route_id not in user.assigned_route_ids and not user._is_global_utility_scope():
            return self._error('ACCESS_DENIED', 'هذا المشترك لا يقع ضمن المسارات المخصصة لك.')

        reading_value = params.get('reading_value')
        if reading_value is None:
            return self._error('VALIDATION_ERROR', 'قيمة القراءة (reading_value) مطلوبة')

        try:
            reading_value = float(reading_value)
        except ValueError:
            return self._error('VALIDATION_ERROR', 'قيمة القراءة يجب أن تكون رقماً')

        period_id = params.get('period_id')
        if not period_id:
            period = request.env['date.range'].search([
                ('period_role', '=', 'reading'),
                ('state', '=', 'open'),
                '|', ('company_id', '=', False), ('company_id', '=', request.env.company.id)
            ], order='date_start desc', limit=1)
            period_id = period.id if period else False

        reading_date = params.get('reading_date', fields.Datetime.now())

        try:
            with request.env.cr.savepoint():
                reading_vals = {
                    'meter_id': meter.id,
                    'customer_id': meter.customer_id.id if meter.customer_id else False,
                    'reading_value': reading_value,
                    'reading_date': reading_date,
                    'reading_purpose': 'periodic',
                    'date_range_id': period_id,
                    'state': 'under_review',  # إرسالها للمراجعة مباشرة
                    'reading_source': 'mobile_app',
                    'notes': params.get('notes', ''),
                    'gps_lat': params.get('gps_lat'),
                    'gps_lng': params.get('gps_lng'),
                }
                
                reading = request.env['utility.reading'].create(reading_vals)

                # معالجة الصورة إن وُجدت
                image_b64 = params.get('image_b64')
                if image_b64:
                    try:
                        decoded = base64.b64decode(image_b64, validate=True)
                        request.env['utility.media.service'].sudo().store_media(
                            file_data=decoded,
                            filename=f"reading_{reading.id}.jpg",
                            mimetype='image/jpeg',
                            reading_id=reading.id,
                            asset_type='meter_reading'
                        )
                        reading.image_state = 'clear'
                    except Exception as e:
                        _logger.error("Failed to save image for reading %s: %s", reading.id, e)

                return {
                    'success': True,
                    'reading_id': reading.id,
                    'state': reading.state,
                }
        except Exception as e:
            _logger.error("Error submitting reading: %s", str(e))
            return self._error('SYSTEM_ERROR', str(e))

class UtilityReaderApiPatch(http.Controller):


    @http.route(
        '/api/v1/utility/reading/check_period_reading',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def check_period_reading(self, meter_code=None, period_id=None, **kwargs):
        """
        التحقق من وجود قراءة للعداد في الفترة المحددة.
        يُستخدم من التطبيق لمنع القراءة المكررة قبل إدخال بيانات جديدة.

        Returns:
            {
                "has_reading": true/false,
                "reading_value": 1234.0,      # إذا has_reading == true
                "reading_date": "2026-08-01", # إذا has_reading == true
            }
        """
        if not meter_code or not period_id:
            return {'has_reading': False, 'error': 'meter_code and period_id are required'}

        # البحث عن العداد
        meter = request.env['utility.meter'].sudo().search(
            [('meter_number', '=', meter_code)], limit=1
        )
        if not meter:
            return {'has_reading': False, 'error': f'Meter {meter_code} not found'}

        # البحث عن الفترة
        period = request.env['date.range'].sudo().browse(period_id)
        if not period.exists():
            return {'has_reading': False, 'error': f'Period {period_id} not found'}

        # البحث عن قراءة دورية للعداد في هذه الفترة
        existing = request.env['utility.reading'].sudo().search([
            ('meter_id', '=', meter.id),
            ('date_range_id', '=', period_id),
            ('reading_purpose', '=', 'periodic'),
            ('active', '=', True),
        ], limit=1, order='reading_date desc')

        if existing:
            return {
                'has_reading': True,
                'reading_value': existing.reading_value,
                'reading_date': str(existing.reading_date) if existing.reading_date else None,
                'reading_id': existing.reading_id,
                'state': existing.state if hasattr(existing, 'state') else 'unknown',
            }

        return {'has_reading': False}
