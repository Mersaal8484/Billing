import logging
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityToken(models.Model):
    _name = 'utility.token'
    _description = 'رمز STS'
    _rec_name = 'token_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company, index=True)
    token_number = fields.Char(string='رقم الكود', index=True)
    token_identifier = fields.Char(string='معرف الكود (TID)', index=True)
    sequence_number = fields.Integer(string='الرقم التسلسلي')

    vending_request_id = fields.Many2one('utility.vending.request', 'طلب البيع',
        index=True, ondelete='set null')
    pos_order_id = fields.Many2one('pos.order', 'أمر نقاط البيع', index=True, ondelete='set null')
    account_id = fields.Many2one('utility.customer', 'الحساب', required=True, index=True)
    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, index=True)
    customer_id = fields.Many2one('res.partner', 'العميل', required=True, index=True)
    contract_template_id = fields.Many2one('utility.contract.template', 'قالب العقد')

    token_type = fields.Selection([
        ('credit', 'رصيد'),
        ('management', 'إدارة'),
        ('key_change', 'تغيير المفتاح'),
        ('test', 'اختبار'),
    ], 'نوع التوكن', default='credit', required=True, index=True)

    amount = fields.Monetary(string='المبلغ', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    kwh = fields.Float(string='كيلوواط ساعة', digits=(12, 3))

    request_date = fields.Datetime(default=fields.Datetime.now, string='تاريخ الطلب')
    response_date = fields.Datetime(string='تاريخ الرد')
    response_code = fields.Char(string='رمز الرد')
    response_message = fields.Text(string='رسالة الرد')

    status = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('success', 'ناجح'),
        ('failed', 'فشل'),
        ('retry', 'إعادة محاولة'),
        ('cancelled', 'ملغى'),
    ], default='pending', string='الحالة', tracking=True, index=True)

    delivery_state = fields.Selection([
        ('not_sent', 'لم يُرسل'),
        ('sms_sent', 'أُرسل عبر SMS'),
        ('printed', 'مطبوع'),
        ('delivered', 'مُسلّم'),
    ], 'حالة التسليم', default='not_sent', tracking=True)

    resend_count = fields.Integer('عدد إعادة الإرسال', default=0)
    reprint_count = fields.Integer('عدد إعادة الطباعة', default=0)
    retry_count = fields.Integer(string='عدد إعادة المحاولة', default=0)
    last_retry_date = fields.Datetime(string='تاريخ آخر محاولة')

    last_resend_date = fields.Datetime('تاريخ آخر إعادة إرسال')
    last_reprint_date = fields.Datetime('تاريخ آخر إعادة طباعة')

    raw_request = fields.Text(string='الطلب الخام')
    raw_response = fields.Text(string='الرد الخام')
    sts_server = fields.Char(string='خادم STS')
    provider_reference = fields.Char('مرجع المزود', index=True)

    mask_display = fields.Char('التوكن المقنع', compute='_compute_mask_display')
    key_change_campaign_id = fields.Many2one('utility.key.change.campaign', 'حملة تغيير المفتاح', index=True)

    _sql_constraints = [
        ('token_number_unique', 'unique(token_number)', 'رقم التوكن يجب أن يكون فريداً.'),
    ]

    @api.depends('token_number')
    def _compute_mask_display(self):
        for rec in self:
            if rec.token_number and len(rec.token_number) > 8:
                rec.mask_display = '****' + rec.token_number[-8:]
            else:
                rec.mask_display = '****'

    def action_request_token(self):
        self.ensure_one()
        self.write({
            'request_date': fields.Datetime.now(),
            'status': 'pending',
        })
        try:
            self._send_token_request()
        except Exception as e:
            _logger.exception('Token request failed for token %s', self.id)
            self.write({
                'status': 'failed',
                'response_date': fields.Datetime.now(),
                'response_code': 'ERROR',
                'response_message': str(e),
                'raw_response': str(e),
            })

    def _send_token_request(self):
        self.ensure_one()
        provider = self.company_id.default_sts_provider_id
        if not provider:
            provider = self.env['utility.sts.provider'].search([
                ('active', '=', True),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
        if not provider:
            raise UserError(_('لا يوجد مزود STS نشط.'))

        meter_ref = self.meter_id.meter_number or self.meter_id.display_name or ''
        order_ref = self.pos_order_id.name or (
            self.vending_request_id.reference if self.vending_request_id else str(self.id))

        self.write({
            'request_date': fields.Datetime.now(),
            'sts_server': provider.name,
            'raw_request': 'REQUEST|provider=%s|amount=%s|kwh=%s|meter=%s|order=%s' % (
                provider.name, self.amount, self.kwh, meter_ref, order_ref,
            ),
        })

        sts_tx = self.env['utility.sts.transaction'].create({
            'vending_request_id': self.vending_request_id.id if self.vending_request_id else False,
            'token_id': self.id,
            'provider_id': provider.id,
            'meter_id': self.meter_id.id,
            'account_id': self.account_id.id,
            'amount': self.amount,
            'kwh': self.kwh,
            'state': 'pending',
        })
        sts_tx.action_send_request()

        if sts_tx.state == 'success' and sts_tx.token_value:
            self.write({
                'token_number': sts_tx.token_value,
                'token_identifier': sts_tx.token_identifier,
                'sequence_number': self.retry_count + 1,
                'response_date': fields.Datetime.now(),
                'response_code': '00',
                'response_message': _('تم إنشاء الرمز بنجاح'),
                'status': 'success',
                'raw_response': sts_tx.raw_response or 'SUCCESS',
                'provider_reference': sts_tx.provider_reference,
            })
        else:
            self.write({
                'status': 'failed',
                'response_date': fields.Datetime.now(),
                'response_code': sts_tx.error_code or 'ERROR',
                'response_message': sts_tx.error_message or _('فشل توليد التوكن'),
                'raw_response': sts_tx.raw_response or 'FAILED',
            })

    def action_retry(self):
        self.ensure_one()
        if self.status in ('success', 'cancelled'):
            raise UserError(_('لا يمكن إعادة محاولة توكن ناجح أو ملغى.'))
        self.write({
            'retry_count': self.retry_count + 1,
            'last_retry_date': fields.Datetime.now(),
            'status': 'retry',
        })
        self.action_request_token()

    def action_cancel(self):
        self.ensure_one()
        if self.status == 'success':
            raise UserError(_('لا يمكن إلغاء توكن تم إنشاؤه بنجاح.'))
        self.write({
            'status': 'cancelled',
            'response_date': fields.Datetime.now(),
            'response_message': _('تم إلغاء طلب الرمز بواسطة المشغل'),
        })

    def action_resend_sms(self):
        self.ensure_one()
        if self.status != 'success':
            raise UserError(_('لا يمكن إعادة إرسال توكن غير ناجح.'))
        limit = self.company_id.token_resend_limit or 5
        if self.resend_count >= limit:
            raise UserError(_('تم تجاوز حد إعادة الإرسال (%d).') % limit)
        self._send_token_sms()
        self.write({
            'resend_count': self.resend_count + 1,
            'last_resend_date': fields.Datetime.now(),
            'delivery_state': 'sms_sent',
        })

    def action_reprint(self):
        self.ensure_one()
        if self.status != 'success':
            raise UserError(_('لا يمكن إعادة طباعة توكن غير ناجح.'))
        if self.company_id.require_reprint_reason and not self.env.context.get('reprint_reason'):
            raise UserError(_('يجب تحديد سبب إعادة الطباعة.'))
        limit = self.company_id.token_reprint_limit or 3
        if self.reprint_count >= limit:
            raise UserError(_('تم تجاوز حد إعادة الطباعة (%d).') % limit)
        self.write({
            'reprint_count': self.reprint_count + 1,
            'last_reprint_date': fields.Datetime.now(),
            'delivery_state': 'printed',
        })

    def _send_token_sms(self):
        self.ensure_one()
        if not self.customer_id or not self.customer_id.phone:
            raise UserError(_('لا يوجد رقم هاتف للعميل.'))
        if not self.token_number:
            raise UserError(_('لا يوجد رمز لإرساله.'))
        try:
            sms_values = {
                'name': _('إرسال رمز STS'),
                'body': _('رمز الشحن: %s\nالعداد: %s\nالطاقة: %s kWh\nالمبلغ: %s') % (
                    self.token_number,
                    self.meter_id.meter_number,
                    self.kwh,
                    self.amount,
                ),
                'number': self.customer_id.phone,
            }
            self.env['sms.sms'].sudo().create(sms_values)
            _logger.info('SMS token sent to %s for token %s', self.customer_id.phone, self.token_number)
        except Exception:
            _logger.exception('Failed to send SMS for token %s', self.id)
            raise UserError(_('فشل إرسال SMS.'))

    def action_mark_delivered(self):
        self.ensure_one()
        self.delivery_state = 'delivered'

    @api.model
    def _cron_send_pending_notifications(self):
        pending_tokens = self.search([
            ('status', '=', 'success'),
            ('delivery_state', '=', 'not_sent'),
            ('customer_id', '!=', False),
        ], limit=200)
        for token in pending_tokens:
            if token.company_id.enable_token_sms and token.customer_id.phone:
                try:
                    token._send_token_sms()
                    token.delivery_state = 'sms_sent'
                except Exception:
                    _logger.exception('Cron SMS failed for token %s', token.id)
