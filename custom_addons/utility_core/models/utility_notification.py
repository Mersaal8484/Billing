from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import re

PHONE_9_RE = re.compile(r'^\d{9}$')


class UtilityNotificationLog(models.Model):
    _name = 'utility.notification.log'
    _description = 'سجل إشعارات الكهرباء'
    _order = 'create_date desc, id desc'

    name = fields.Char('العنوان', required=True)
    channel = fields.Selection([
        ('sms', 'رسائل قصيرة (SMS)'),
        ('portal', 'البوابة'),
        ('internal', 'داخلي'),
    ], string='القناة', required=True, default='internal')
    event_type = fields.Selection([
        ('invoice_created', 'إصدار فاتورة'),
        ('payment_received', 'استلام دفعة'),
        ('bill_overdue', 'فاتورة متأخرة'),
        ('service_order', 'أمر خدمة'),
    ], string='نوع الحدث', required=True)
    customer_id = fields.Many2one('utility.customer', string='الحساب', index=True)
    partner_id = fields.Many2one('res.partner', string='الشريك', index=True)
    mobile = fields.Char('رقم الجوال')
    subject = fields.Char('الموضوع')
    body = fields.Text('نص الرسالة', required=True)
    model_name = fields.Char('النموذج')
    res_id = fields.Integer('معرف السجل')
    state = fields.Selection([
        ('queued', 'في الانتظار'),
        ('sent', 'مرسل'),
        ('failed', 'فشل'),
        ('cancelled', 'ملغى'),
    ], string='الحالة', default='queued', required=True, index=True)
    error_message = fields.Text('رسالة الخطأ')
    sent_date = fields.Datetime('تاريخ الإرسال')

    @api.model
    def create_log(self, event_type, body, record=None, customer=None, partner=None, channel='internal', subject=False):
        customer = customer or getattr(record, 'customer_id', False)
        partner = partner or getattr(record, 'partner_id', False) or (customer.partner_id if customer else False)
        return self.create({
            'name': subject or dict(self._fields['event_type'].selection).get(event_type, event_type),
            'channel': channel,
            'event_type': event_type,
            'customer_id': customer.id if customer else False,
            'partner_id': partner.id if partner else False,
            'mobile': partner.mobile or partner.phone if partner else False,
            'subject': subject or False,
            'body': body,
            'model_name': record._name if record else False,
            'res_id': record.id if record else False,
            'state': 'queued',
        })

    @api.constrains('mobile')
    def _check_phone_9_digits(self):
        for rec in self:
            if rec.mobile and not PHONE_9_RE.match(rec.mobile):
                raise ValidationError(
                    'رقم الجوال يجب أن يتكون من 9 أرقام فقط، بدون مفتاح دولة (+967/00) أو شرطات.'
                )

    def action_dispatch(self):
        sms_provider = self.env['utility.integration.provider'].sudo().search([
            ('provider_type', '=', 'sms'),
            ('active', '=', True),
        ], limit=1)
        for notification in self.filtered(lambda n: n.channel == 'sms' and n.state == 'queued'):
            if not sms_provider:
                notification.write({
                    'state': 'failed',
                    'error_message': _('لا يوجد مزود SMS نشط.'),
                })
                continue
            payload = {
                'to': notification.mobile,
                'message': notification.body,
                'customer': notification.customer_id.customer_number if notification.customer_id else False,
                'event_type': notification.event_type,
            }
            log = sms_provider.call_json(payload, 'sms.%s' % notification.event_type, record=notification)
            if log.state == 'success':
                notification.write({'state': 'sent', 'sent_date': fields.Datetime.now(), 'error_message': False})
            else:
                notification.write({'state': 'failed', 'error_message': log.error_message})
        return True

    @api.model
    def cron_dispatch_sms_notifications(self):
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param('utility.sms_batch_size', 200))
        notifications = self.search([
            ('channel', '=', 'sms'),
            ('state', '=', 'queued'),
        ], limit=batch_size, order='create_date asc, id asc')
        notifications.action_dispatch()
        return len(notifications)
