import base64
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
    _inherit = ['mail.thread', 'mail.activity.mixin', 'utility.dropdown.mixin']
    _rec_name = 'name'
    _order = 'upload_date desc'

    name = fields.Char('رقم الدفعة', readonly=True, default=lambda self: _('New'))
    user_id = fields.Many2one('res.users', 'القارئ / الجابي',
                              default=lambda self: self.env.user, tracking=True)
    upload_date = fields.Datetime('تاريخ الرفع', default=fields.Datetime.now,
                                  readonly=True)
    available_open_reading_period_ids = fields.Many2many('date.range', compute='_compute_available_open_reading_period_ids')
    date_range_id = fields.Many2one('date.range', string='الفترة (الشهر)', required=True)
    region_id = fields.Many2one('utility.region', string='المنطقة', domain="[('type', '=', 'region')]")
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
    processed_offset = fields.Integer('مؤشر التقدم داخل الملف', readonly=True, default=0)
    progress_percent = fields.Float('نسبة التقدم %', compute='_compute_progress_percent', store=True)

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

    @api.depends('processed_count', 'error_count', 'total_readings')
    def _compute_progress_percent(self):
        for batch in self:
            if batch.total_readings > 0:
                done = batch.processed_count + batch.error_count
                batch.progress_percent = min(100.0, round(done / batch.total_readings * 100, 1))
            else:
                batch.progress_percent = 0.0

    @api.depends('region_id.recurring_rule_type')
    def _compute_available_open_reading_period_ids(self):
        for rec in self:
            billing_period = rec.region_id.recurring_rule_type if rec.region_id else False
            region_id = rec.region_id.id if rec.region_id else False
            domain = self._get_open_period_domain(work_type='readings', billing_period=billing_period, region_id=region_id)
            rec.available_open_reading_period_ids = self.env['date.range'].search(domain)

    @api.onchange('region_id')
    def _onchange_region_id_date_range(self):
        available_periods = self.available_open_reading_period_ids
        if self.date_range_id and self.date_range_id not in available_periods:
            self.date_range_id = False
        return {'domain': {'date_range_id': [('id', 'in', available_periods.ids)]}}

    @api.constrains('date_range_id', 'region_id', 'upload_date')
    def _check_batch_period_rules(self):
        for batch in self:
            if not batch.date_range_id:
                continue
            period = batch.date_range_id
            if period.period_role != 'reading':
                raise ValidationError(_('دفعة الرفع يجب أن تُربط بفترة قراءة وفوترة.'))

            if batch.region_id:
                cadence = 'semi_monthly' if batch.region_id.recurring_rule_type == 'biweekly' else batch.region_id.recurring_rule_type
                if period.billing_cadence != cadence:
                    raise ValidationError(_(
                        'دورية المنطقة (%s) لا تطابق دورية الفترة المختارة (%s).'
                    ) % (batch.region_id.recurring_rule_type, period.billing_cadence))
                if period.region_ids and batch.region_id not in period.region_ids:
                    raise ValidationError(_(
                        'المنطقة المحدد للدفعة (%s) غير مشمولة في نطاق مناطق هذه الفترة.'
                    ) % batch.region_id.name)

            if period.reading_window_end and batch.upload_date and batch.upload_date > period.reading_window_end:
                raise ValidationError(_(
                    'تاريخ رفع الدفعة (%s) يتجاوز نافذة القراءة المسموحة للفترة (%s).'
                ) % (batch.upload_date, period.reading_window_end))

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
                json_data = json.loads(base64.b64decode(batch.data_file))
                readings_data = json_data.get('readings', [])
                batch.write({
                    'total_readings': len(readings_data),
                    'processed_count': 0,
                    'error_count': 0,
                    'processed_offset': 0,
                    'error_log': False,
                })
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
                'processed_count': 0,
                'error_count': 0,
                'processed_offset': 0,
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
                json_data = json.loads(base64.b64decode(batch.data_file))
            except Exception as e:
                batch.write({
                    'state': 'error',
                    'error_log': f'فشل في قراءة ملف JSON: {e}',
                })
                continue

            readings_data = json_data.get('readings', [])
            start = batch.processed_offset or 0
            to_process = readings_data[start:start + batch_size]
            if not to_process:
                batch.write({
                    'state': 'done' if not batch.error_count else 'partial',
                    'total_readings': batch.total_readings or len(readings_data),
                })
                continue
            error_log_lines = []
            processed = 0

            image_attachments = {}
            for att in batch.image_ids:
                image_attachments[att.name] = att

            for entry in to_process:
                seq = entry.get('seq', '?')
                meter_number = entry.get('meter_number')
                try:
                    with self.env.cr.savepoint():
                        if not meter_number:
                            raise ValueError('رقم العداد مفقود')

                        meter = Meter.search([
                            ('meter_number', '=', meter_number)
                        ], limit=1)
                        if not meter:
                            raise ValueError(
                                f'العداد "{meter_number}" غير موجود في النظام')

                        reading_date = entry.get('reading_date') or fields.Datetime.now()
                        existing_reading = Reading.search([
                            ('batch_id', '=', batch.id),
                            ('meter_id', '=', meter.id),
                            ('date_range_id', '=', batch.date_range_id.id),
                            ('reading_date', '=', reading_date),
                        ], limit=1)
                        if existing_reading:
                            processed += 1
                            continue

                        image_filename = entry.get('image_filename', '')
                        image_data = False
                        if image_filename and image_filename in image_attachments:
                            image_data = image_attachments[image_filename].datas

                        Reading.create({
                            'meter_id': meter.id,
                            'reading_value': entry.get('reading_value', 0),
                            'reading_date': reading_date,
                            'date_range_id': batch.date_range_id.id,
                            'reading_category': entry.get('reading_category', 'customer'),
                            'meter_image': image_data,
                            'remarks': entry.get('remarks', ''),
                            'reading_source': f'batch_{batch.name}',
                            'batch_id': batch.id,
                        })
                        processed += 1

                except Exception as exc:
                    error_log_lines.append(
                        f'[{seq}] {meter_number}: {str(exc)}')
            error_count = len(error_log_lines)
            total_processed = batch.processed_count + processed
            total_errors = batch.error_count + error_count
            next_offset = start + len(to_process)
            total_readings = batch.total_readings or len(readings_data)

            if next_offset >= total_readings:
                final_state = 'done' if total_errors == 0 else 'partial'
            else:
                final_state = 'processing'

            previous_log = batch.error_log or ''
            new_log = '\n'.join(error_log_lines)
            batch.write({
                'processed_count': total_processed,
                'error_count': total_errors,
                'processed_offset': next_offset,
                'total_readings': total_readings,
                'state': final_state,
                'error_log': '\n'.join([l for l in [previous_log, new_log] if l]) or False,
            })

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
            if batch.data_file:
                json_att = Attachment.search([
                    ('res_model', '=', 'utility.reading.batch'),
                    ('res_id', '=', batch.id),
                    ('res_field', '=', 'data_file'),
                ], limit=1)
                if json_att:
                    json_att.unlink()
                batch.data_file = False

            if batch.image_ids:
                batch.image_ids.unlink()

            batch.message_post(
                body=f'تم حذف ملفات الدفعة تلقائياً بعد {retention_days} يوماً من الرفع.'
            )

        _logger.info('Batch Cleanup: cleaned %d old batches', len(old_batches))
