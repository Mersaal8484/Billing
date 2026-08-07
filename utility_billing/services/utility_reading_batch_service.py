import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UtilityReadingBatchService(models.AbstractModel):
    _name = 'utility.reading.batch.service'
    _description = 'مخدم معالجة دفعات القراءات (Reading Batch Processing Service)'

    @api.model
    def process_batch(self, batch_id, chunk_size=500):
        """معالجة دفعة قراءات بشكل مجزأ (Chunked Batch Processing) مع عزل الأخطاء وتوثيق الأصول الرقمية"""
        batch = self.env['utility.reading.batch'].sudo().browse(batch_id)
        if not batch or not batch.exists():
            raise ValidationError(_("دفعة القراءات غير موجودة."))

        _logger.info("Starting service batch processing for batch %s (Chunk Size: %d)", batch.name, chunk_size)

        batch.write({
            'state': 'processing',
        })

        data_json = batch._get_parsed_json_data()
        readings_raw = data_json.get('readings', []) if isinstance(data_json, dict) else []

        if not readings_raw:
            batch.write({
                'state': 'error',
                'error_log': _("الملف المرفق لا يحتوي على قائمة قراءات صالحة (readings)."),
            })
            return {'status': 'failed', 'reason': 'empty_data'}

        # 1. البحث في الأصول الرقمية المرفوعة بدفعة القراءات (utility.media.asset)
        media_assets = self.env['utility.media.asset'].sudo().search([
            ('batch_id', '=', batch.id),
            ('asset_type', '=', 'meter_reading'),
        ])
        media_assets_by_name = {asset.original_filename: asset for asset in media_assets}

        # 2. التوافقية السابقة: البحث في مرفقات ir.attachment الدفعة
        legacy_attachments = {att.name: att for att in batch.image_ids}
        
        success_count = 0
        error_count = 0
        logs = []

        # معالجة القراءات مجزأة بحجم chunk_size
        total_items = len(readings_raw)
        for i in range(0, total_items, chunk_size):
            chunk = readings_raw[i:i + chunk_size]
            _logger.info("Processing batch %s chunk %d to %d of %d", batch.name, i, i + len(chunk), total_items)
            
            for item in chunk:
                try:
                    res = self._process_single_reading_item(batch, item, media_assets_by_name, legacy_attachments)
                    if res.get('success'):
                        success_count += 1
                    else:
                        error_count += 1
                        logs.append(res.get('error', _('خطأ غير معروف')))
                except Exception as e:
                    error_count += 1
                    error_msg = f"متر {item.get('meter_number', 'N/A')}: {str(e)}"
                    logs.append(error_msg)
                    _logger.error("Single reading item processing error: %s", error_msg)

        # حساب الحالة النهائية الصالحة (done / partial / error)
        if success_count > 0 and error_count > 0:
            final_state = 'partial'
        elif success_count > 0:
            final_state = 'done'
        else:
            final_state = 'error'

        log_text = "\n".join(logs) if logs else _("تمت المعالجة بنجاح دون أخطاء.")

        batch.write({
            'state': final_state,
            'processed_count': success_count,
            'error_count': error_count,
            'error_log': log_text,
        })

        _logger.info("Completed batch processing %s: %d success, %d errors, state: %s", batch.name, success_count, error_count, final_state)
        return {
            'status': 'completed',
            'success_count': success_count,
            'error_count': error_count,
            'final_state': final_state,
        }

    @api.model
    def _process_single_reading_item(self, batch, item, media_assets_by_name, legacy_attachments):
        meter_number = item.get('meter_number')
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

        reading_value = item.get('reading_value', 0.0)
        reading_date = item.get('reading_date') or fields.Datetime.now()
        image_filename = item.get('image_filename')

        # معالجة الصورة الرقمية عبر Media Service أو المرفقات السابقة
        media_asset = False
        if image_filename:
            if image_filename in media_assets_by_name:
                media_asset = media_assets_by_name[image_filename]
            elif image_filename in legacy_attachments:
                att = legacy_attachments[image_filename]
                try:
                    media_asset = MediaService.store_media(
                        file_data=att.datas,
                        filename=att.name,
                        mimetype=att.mimetype or 'image/jpeg',
                        batch_id=batch.id,
                        asset_type='meter_reading'
                    )
                except Exception as e:
                    _logger.warning("Could not store media asset for %s: %s", image_filename, str(e))

        # إنشاء سجل القراءة المعتمد
        reading_vals = {
            'meter_id': meter.id,
            'account_id': customer.id,
            'date_range_id': batch.date_range_id.id,
            'reading_value': reading_value,
            'reading_date': reading_date,
            'reading_purpose': 'periodic',
            'state': 'approved' if not item.get('has_anomaly') else 'under_review',
        }

        if media_asset:
            reading_vals['image_asset_id'] = media_asset.id
            if media_asset.original_attachment_id:
                reading_vals['attachment_id'] = media_asset.original_attachment_id.id

        reading = Reading.create(reading_vals)
        if media_asset and not media_asset.reading_id:
            media_asset.write({'reading_id': reading.id})

        return {'success': True, 'reading_id': reading.id}
