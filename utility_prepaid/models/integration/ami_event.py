import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UtilityPrepaidAmiEvent(models.Model):
    _name = 'utility.prepaid.ami.event'
    _description = 'حدث AMI للدفع المسبق'
    _rec_name = 'reference'
    _order = 'event_date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company, index=True)
    reference = fields.Char('المرجع', required=True, copy=False, index=True, default=lambda self: _('جديد'))
    event_date = fields.Datetime('تاريخ الحدث', default=fields.Datetime.now, index=True)

    event_type = fields.Selection([
        ('low_credit', 'رصيد منخفض'),
        ('zero_credit', 'رصيد صفر'),
        ('token_accepted', 'تم قبول التوكن'),
        ('token_rejected', 'تم رفض التوكن'),
        ('meter_disconnected', 'انفصال العداد'),
        ('meter_reconnected', 'إعادة اتصال العداد'),
        ('tamper', 'حدث تلاعب'),
        ('balance_update', 'تحديث الرصيد'),
    ], 'نوع الحدث', required=True, index=True)

    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, index=True)
    account_id = fields.Many2one('utility.customer', 'الحساب', index=True)
    token_id = fields.Many2one('utility.token', 'التوكن', index=True)

    event_value = fields.Float('قيمة الحدث', digits=(12, 3),
        help='قيمة الرصيد أو الاستهلاك المرتبط بالحدث')
    event_data = fields.Text('بيانات الحدث (JSON)',
        help='البيانات الخام للحدث بصيغة JSON')

    processed = fields.Boolean('تمت المعالجة', default=False, index=True)
    processed_date = fields.Datetime('تاريخ المعالجة')
    processing_result = fields.Text('نتيجة المعالجة')

    severity = fields.Selection([
        ('info', 'معلومات'),
        ('warning', 'تحذير'),
        ('critical', 'حرج'),
    ], 'الخطورة', default='info', index=True)

    notification_sent = fields.Boolean('تم إرسال إشعار', default=False)
    support_ticket_created = fields.Boolean('تم إنشاء تذكرة دعم', default=False)

    raw_payload = fields.Text('البيانات الخام')
    source = fields.Char('المصدر',
        help='نظام AMI أو MDMS المرسل')

    notes = fields.Text('ملاحظات')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('جديد')) == _('جديد'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('utility.prepaid.ami.event') or _('جديد')
        return super().create(vals_list)

    def action_process(self):
        for rec in self:
            if rec.processed:
                continue
            rec._process_event()

    def _process_event(self):
        self.ensure_one()
        try:
            if self.event_type in ('low_credit', 'zero_credit'):
                self._handle_credit_event()
            elif self.event_type == 'token_accepted':
                self._handle_token_accepted()
            elif self.event_type == 'token_rejected':
                self._handle_token_rejected()
            elif self.event_type == 'balance_update':
                self._handle_balance_update()

            self.write({
                'processed': True,
                'processed_date': fields.Datetime.now(),
                'processing_result': _('تمت المعالجة بنجاح'),
            })
        except Exception as e:
            _logger.exception('Failed to process AMI event %s', self.reference)
            self.write({
                'processed': True,
                'processed_date': fields.Datetime.now(),
                'processing_result': _('فشل المعالجة: %s') % str(e),
            })

    def _handle_credit_event(self):
        self.ensure_one()
        if self.company_id.enable_low_credit_alert and self.account_id and self.account_id.partner_id:
            phone = self.account_id.partner_id.phone or self.account_id.partner_id.mobile
            if phone:
                try:
                    if self.event_type == 'low_credit':
                        body = _('تنبيه: رصيد الكهرباء منخفض. الرصيد الحالي: %s kWh') % self.event_value
                    else:
                        body = _('تنبيه: رصيد الكهرباء نفد. يرجى شحن العداد.')
                    self.env['sms.sms'].sudo().create({
                        'name': _('تنبيه رصيد منخفض'),
                        'body': body,
                        'number': phone,
                    })
                    self.notification_sent = True
                    _logger.info('Low credit SMS sent to %s for meter %s', phone, self.meter_id.meter_number)
                except Exception:
                    _logger.exception('Failed to send low credit SMS')

    def _handle_token_accepted(self):
        self.ensure_one()
        if self.token_id:
            self.token_id.write({
                'delivery_state': 'delivered',
            })

    def _handle_token_rejected(self):
        self.ensure_one()
        _logger.warning('Token rejected for meter %s: %s',
            self.meter_id.meter_number, self.event_data)

    def _handle_balance_update(self):
        self.ensure_one()
        if self.account_id:
            self.account_id.write({
                'last_reading_value': self.event_value,
                'last_reading_date': self.event_date,
            })

    @api.model
    def _cron_process_low_credit(self):
        unprocessed = self.search([
            ('processed', '=', False),
            ('event_type', 'in', ('low_credit', 'zero_credit')),
        ], limit=100)
        for event in unprocessed:
            try:
                event._process_event()
            except Exception:
                _logger.exception('Cron processing failed for AMI event %s', event.reference)

    @api.model
    def _cron_process_unprocessed(self):
        unprocessed = self.search([
            ('processed', '=', False),
        ], limit=200)
        for event in unprocessed:
            try:
                event.action_process()
            except Exception:
                _logger.exception('Cron processing failed for AMI event %s', event.reference)
