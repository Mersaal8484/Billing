import base64
import json
import logging
from psycopg2 import OperationalError
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UtilityReadingBatchService(models.AbstractModel):
    _name = 'utility.reading.batch.service'
    _description = 'مخدم معالجة دفعات القراءات (Reading Batch Processing Service)'

    @api.model
    def process_batch(self, batch_id, chunk_size=500):
        """معالجة أسطر الدفعة بشكل مجزأ (Chunked Persistent Lines) مع عزل الأخطاء ومعالجة الأسطر المعلقة/الفاشلة فقط عند إعادة المحاولة"""
        batch = self.env['utility.reading.batch'].sudo().browse(batch_id)
        if not batch or not batch.exists():
            raise ValidationError(_("دفعة القراءات غير موجودة."))

        try:
            self.env.cr.execute(
                "SELECT id FROM utility_reading_batch WHERE id = %s FOR UPDATE NOWAIT",
                (batch_id,)
            )
        except OperationalError as e:
            pgcode = getattr(e, 'pgcode', None)
            if pgcode == '55P03':
                _logger.info("Reading batch %s is currently locked by another worker (55P03). Skipping concurrent execution.", batch.id)
                return {'status': 'locked', 'reason': 'batch_locked'}
            raise

        _logger.info("Starting persistent line batch processing for batch %s", batch.name)

        batch.write({
            'state': 'processing',
        })

        # 1. إنشاء الأسطر التفصيلية المستمرة (utility.reading.batch.line) إذا لم تكن موجودة بعد
        if not batch.line_ids:
            data_json = batch._get_parsed_json_data()
            readings_raw = data_json.get('readings', []) if isinstance(data_json, dict) else []
            if not readings_raw:
                batch.write({
                    'state': 'error',
                    'error_log': _("الملف المرفق لا يحتوي على قائمة قراءات صالحة (readings)."),
                })
                return {'status': 'failed', 'reason': 'empty_data'}

            line_vals = []
            for item in readings_raw:
                line_vals.append({
                    'batch_id': batch.id,
                    'seq': item.get('seq', 1),
                    'meter_number': item.get('meter_number'),
                    'reading_value': item.get('reading_value', 0.0),
                    'reading_date': item.get('reading_date') or fields.Datetime.now(),
                    'reading_category': item.get('reading_category', 'customer'),
                    'image_filename': item.get('image_filename'),
                    'state': 'pending',
                })
            self.env['utility.reading.batch.line'].sudo().create(line_vals)

        # 2. البحث في الأصول الرقمية والمرفقات لتحديد الوسائط
        media_assets = self.env['utility.media.asset'].sudo().search([
            ('batch_id', '=', batch.id),
            ('asset_type', '=', 'meter_reading'),
        ])
        media_assets_by_name = {asset.original_filename: asset for asset in media_assets}
        legacy_attachments = {att.name: att for att in batch.image_ids}

        # 3. اختيار الأسطر التي تحتاج المعالجة فقط (pending أو failed) — يتجاوز الأسطر المكتملة بنجاح (done)
        pending_lines = batch.line_ids.filtered(lambda l: l.state in ('pending', 'failed'))
        _logger.info("Batch %s has %d lines pending/failed to process out of %d total lines",
                     batch.name, len(pending_lines), len(batch.line_ids))

        # معالجة مجزأة بحجم chunk_size
        total_pending = len(pending_lines)
        for i in range(0, total_pending, chunk_size):
            chunk = pending_lines[i:i + chunk_size]
            for line in chunk:
                try:
                    res = self._process_single_batch_line(batch, line, media_assets_by_name, legacy_attachments)
                    if res.get('success'):
                        line.write({
                            'state': 'done',
                            'reading_id': res.get('reading_id'),
                            'error_message': False,
                        })
                    else:
                        line.write({
                            'state': 'failed',
                            'error_message': res.get('error', _('خطأ غير معروف')),
                        })
                except Exception as e:
                    error_msg = str(e)
                    line.write({
                        'state': 'failed',
                        'error_message': error_msg,
                    })
                    _logger.error("Single batch line processing error: %s", error_msg)

        # 4. تحديث حالة الدفعة الكلية من واقع كافّة الأسطر (done / partial / error)
        all_lines = batch.line_ids
        done_count = len(all_lines.filtered(lambda l: l.state == 'done'))
        failed_count = len(all_lines.filtered(lambda l: l.state == 'failed'))
        total_count = len(all_lines)

        if done_count == total_count and total_count > 0:
            final_state = 'done'
        elif done_count > 0:
            final_state = 'partial'
        else:
            final_state = 'error'

        failed_messages = [f"متر {l.meter_number}: {l.error_message}" for l in all_lines if l.state == 'failed']
        log_text = "\n".join(failed_messages) if failed_messages else _("تمت المعالجة بنجاح دون أخطاء.")

        batch.write({
            'state': final_state,
            'total_readings': total_count,
            'processed_count': done_count,
            'error_count': failed_count,
            'error_log': log_text,
        })

        _logger.info("Completed batch processing %s: %d done, %d failed out of %d, state: %s",
                     batch.name, done_count, failed_count, total_count, final_state)

        return {
            'status': 'completed',
            'success_count': done_count,
            'error_count': failed_count,
            'final_state': final_state,
        }

    @api.model
    def _validate_batch_line_scope(self, batch, meter, customer):
        """التحقق من وقوع العداد والمشترك ضمن النطاق التنظيمي للقارئ ومنطقة الدفعة."""
        # 1. التحقق من تطابق منطقة الدفعة مع منطقة العداد/المشترك إن وُجدت
        if batch.region_id:
            meter_region = getattr(meter, 'region_id', False) or (customer.region_id if customer else False)
            if meter_region and meter_region.id != batch.region_id.id:
                return {
                    'valid': False,
                    'error': _("العداد يقع في منطقة (%s) تختلف عن منطقة الدفعة (%s).") % (
                        meter_region.name, batch.region_id.name
                    )
                }

        # 2. التحقق من صلاحيات القارئ الجغرافية والتنظيمية
        if batch.user_id and hasattr(batch.user_id, 'check_record_scope'):
            try:
                batch.user_id.check_record_scope(meter)
            except AccessError:
                return {
                    'valid': False,
                    'error': _("العداد %s يقع خارج النطاق الجغرافي/التنظيمي المخصص للقارئ %s.") % (
                        meter.meter_number, batch.user_id.name
                    )
                }

        return {'valid': True}

    @api.model
    def _process_single_batch_line(self, batch, line, media_assets_by_name, legacy_attachments):
        meter_number = line.meter_number
        if not meter_number:
            return {'success': False, 'error': _("رمز العداد غير موجود في السجل.")}

        Meter = self.env['utility.meter'].sudo()
        Reading = self.env['utility.reading'].sudo()
        MediaService = self.env['utility.media.service'].sudo()

        meter = Meter.search([('meter_number', '=', meter_number)], limit=1)
        if not meter:
            return {'success': False, 'error': _("العداد رقم %s غير موجود بالمنظومة.") % meter_number}

        customer = meter.customer_id
        if not customer:
            return {'success': False, 'error': _("العداد %s غير مرتبط بمشترك/حساب.") % meter_number}

        # التحقق من نطاق الصلاحيات التنظيمية للدفعة
        scope_res = self._validate_batch_line_scope(batch, meter, customer)
        if not scope_res.get('valid'):
            return {'success': False, 'error': scope_res.get('error')}

        reading_value = line.reading_value
        reading_date = line.reading_date or fields.Datetime.now()
        image_filename = line.image_filename

        # معالجة الصورة الرقمية عبر Media Service أو المرفقات السابقة
        media_asset = False
        if image_filename:
            if image_filename in media_assets_by_name:
                media_asset = media_assets_by_name[image_filename]
            elif image_filename in legacy_attachments:
                att = legacy_attachments[image_filename]
                try:
                    raw = att.datas
                    if isinstance(raw, str):
                        raw = base64.b64decode(raw)
                    media_asset = MediaService.store_media(
                        file_data=raw,
                        filename=att.name,
                        mimetype=att.mimetype or 'image/jpeg',
                        batch_id=batch.id,
                        asset_type='meter_reading'
                    )
                except Exception as e:
                    _logger.warning("Could not store media asset for %s: %s", image_filename, str(e))

        reading_state = 'under_review'
        reading_vals = {
            'meter_id': meter.id,
            'account_id': customer.id,
            'date_range_id': batch.date_range_id.id,
            'reading_value': reading_value,
            'reading_date': reading_date,
            'reading_purpose': 'periodic',
            'state': reading_state,
        }

        if media_asset:
            reading_vals['image_asset_id'] = media_asset.id
            if media_asset.original_attachment_id:
                reading_vals['attachment_id'] = media_asset.original_attachment_id.id

        reading = Reading.create(reading_vals)
        if media_asset and not media_asset.reading_id:
            media_asset.write({'reading_id': reading.id})

        return {'success': True, 'reading_id': reading.id}
