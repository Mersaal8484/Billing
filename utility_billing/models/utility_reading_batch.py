import json
import logging
import os
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UtilityReadingBatch(models.Model):
    _name = 'utility.reading.batch'
    _description = 'دفعة رفع قراءات'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'upload_date desc'

    name = fields.Char('رقم الدفعة', readonly=True, default=lambda self: _('New'))
    user_id = fields.Many2one('res.users', 'القارئ / الجابي',
                              default=lambda self: self.env.user, tracking=True)
    upload_date = fields.Datetime('تاريخ الرفع', default=fields.Datetime.now,
                                  readonly=True)
    date_range_id = fields.Many2one('date.range', string='الفترة (الشهر)',
                                    required=True)
    region_id = fields.Many2one('utility.region', string='المنطقة')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    # بيانات القراءات (JSON خفيف بدون صور)
    data_file = fields.Binary('ملف البيانات (JSON)', attachment=True)
    data_filename = fields.Char('اسم ملف البيانات')

    # الصور كمرفقات منفصلة مرتبطة بالسجل
    image_ids = fields.One2many('ir.attachment', 'res_id',
                                domain=[('res_model', '=', 'utility.reading.batch')],
                                string='صور العدادات')

    total_readings = fields.Integer('إجمالي القراءات', readonly=True)
    processed_count = fields.Integer('تمت معالجتها', readonly=True, default=0)
    error_count = fields.Integer('فشلت', readonly=True, default=0)

    state = fields.Selection([
        ('uploaded', 'تم الرفع'),
        ('processing', 'قيد المعالجة'),
        ('done', 'مكتمل'),
        ('partial', 'مكتمل جزئياً'),
        ('error', 'خطأ'),
    ], default='uploaded', string='الحالة', tracking=True)

    error_log = fields.Text('سجل الأخطاء', readonly=True)
    reading_ids = fields.One2many('utility.reading', 'batch_id',
                                  string='القراءات المُنشأة')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'utility.reading.batch') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        """تأكيد اكتمال الرفع — بدء المعالجة عبر الـ Cron"""
        for batch in self:
            if batch.state != 'uploaded':
                raise ValidationError('يمكن تأكيد الدفعات التي بحالة "تم الرفع" فقط!')
            if not batch.data_file:
                raise ValidationError('لم يتم رفع ملف البيانات (JSON)!')

            # حساب عدد القراءات من الملف
            try:
                import base64
                json_data = json.loads(base64.b64decode(batch.data_file))
                readings_data = json_data.get('readings', [])
                batch.total_readings = len(readings_data)
            except Exception as e:
                raise ValidationError(f'خطأ في قراءة ملف JSON: {e}')

            batch.state = 'processing'

    def action_reset_to_uploaded(self):
        """إعادة الدفعة إلى حالة تم الرفع لمحاولة المعالجة مرة أخرى"""
        for batch in self:
            if batch.state not in ('error', 'partial'):
                raise ValidationError('يمكن إعادة المحاولة فقط للدفعات بحالة خطأ أو مكتمل جزئياً!')
            batch.write({
                'state': 'processing',
                'error_log': False,
            })

    @api.model
    def _cron_process_readings(self):
        """مهمة مجدولة: معالجة دفعات القراءات المرفوعة"""
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'utility.reading_upload_batch_size', 100))

        batches = self.search([('state', '=', 'processing')], limit=5)
        if not batches:
            return

        Meter = self.env['utility.meter']
        Reading = self.env['utility.reading']

        for batch in batches:
            try:
                import base64
                json_data = json.loads(base64.b64decode(batch.data_file))
            except Exception as e:
                batch.write({
                    'state': 'error',
                    'error_log': f'فشل في قراءة ملف JSON: {e}',
                })
                self.env.cr.commit()
                continue

            readings_data = json_data.get('readings', [])
            # معالجة حتى batch_size قراءة فقط من كل دفعة
            to_process = readings_data[:batch_size]
            error_log_lines = []
            processed = 0

            # جلب أسماء صور المرفقة
            image_attachments = {}
            for att in batch.image_ids:
                image_attachments[att.name] = att

            for entry in to_process:
                seq = entry.get('seq', '?')
                meter_number = entry.get('meter_number')
                try:
                    if not meter_number:
                        raise ValueError('رقم العداد مفقود')

                    meter = Meter.search([
                        ('meter_number', '=', meter_number)
                    ], limit=1)
                    if not meter:
                        raise ValueError(
                            f'العداد "{meter_number}" غير موجود في النظام')

                    # البحث عن صورة مطابقة
                    image_filename = entry.get('image_filename', '')
                    image_data = False
                    if image_filename and image_filename in image_attachments:
                        image_data = image_attachments[image_filename].datas

                    reading = Reading.create({
                        'meter_id': meter.id,
                        'reading_value': entry.get('reading_value', 0),
                        'reading_date': entry.get('reading_date') or fields.Datetime.now(),
                        'date_range_id': batch.date_range_id.id,
                        'reading_category': entry.get('reading_category', 'customer'),
                        'meter_image': image_data,
                        'remarks': entry.get('remarks', ''),
                        'reading_source': f'batch_{batch.name}',
                        'batch_id': batch.id,
                    })
                    processed += 1
                    self.env.cr.commit()

                except Exception as e:
                    self.env.cr.rollback()
                    error_log_lines.append(
                        f'[{seq}] {meter_number}: {str(e)}')
                    self.env.cr.commit()

            # تحديث حالة الدفعة
            error_count = len(error_log_lines)
            total_processed = batch.processed_count + processed
            total_errors = batch.error_count + error_count

            if total_processed + total_errors >= batch.total_readings:
                # اكتملت المعالجة
                final_state = 'done' if total_errors == 0 else 'partial'
            else:
                final_state = 'processing'  # لا تزال هناك قراءات متبقية

            batch.write({
                'processed_count': total_processed,
                'error_count': total_errors,
                'state': final_state,
                'error_log': '\n'.join(error_log_lines) if error_log_lines else batch.error_log,
            })
            self.env.cr.commit()

            _logger.info(
                'Batch %s: processed %d, errors %d, state %s',
                batch.name, processed, error_count, final_state
            )

    @api.model
    def _cron_cleanup_old_batches(self):
        """مهمة مجدولة: حذف ملفات الدفعات المكتملة بعد فترة الاحتفاظ"""
        retention_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'utility.batch_file_retention_days', 30))
        cutoff_date = fields.Datetime.now() - timedelta(days=retention_days)

        old_batches = self.search([
            ('state', 'in', ('done', 'partial')),
            ('upload_date', '<', cutoff_date),
        ])

        Attachment = self.env['ir.attachment']
        for batch in old_batches:
            # حذف ملف الـ JSON
            if batch.data_file:
                json_att = Attachment.search([
                    ('res_model', '=', 'utility.reading.batch'),
                    ('res_id', '=', batch.id),
                    ('res_field', '=', 'data_file'),
                ], limit=1)
                if json_att:
                    json_att.unlink()
                batch.data_file = False

            # حذف الصور المرفقة
            if batch.image_ids:
                batch.image_ids.unlink()

            batch.message_post(
                body=f'تم حذف ملفات الدفعة تلقائياً بعد {retention_days} يوماً من الرفع.'
            )
            self.env.cr.commit()

        _logger.info('Batch Cleanup: cleaned %d old batches', len(old_batches))
