import logging
from datetime import datetime

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class UtilityToken(models.Model):
    _name = 'utility.token'
    _description = 'رمز STS'
    _rec_name = 'token_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    token_number = fields.Char(string='رقم الكود', index=True)
    token_identifier = fields.Char(string='معرف الكود (TID)')
    sequence_number = fields.Integer(string='الرقم التسلسلي')
    pos_order_id = fields.Many2one('pos.order', string='أمر نقاط البيع', required=True, ondelete='cascade')
    account_id = fields.Many2one('utility.customer', string='الحساب', required=True)
    meter_id = fields.Many2one('utility.meter', string='العداد', required=True)
    customer_id = fields.Many2one('res.partner', string='العميل', required=True)
    contract_template_id = fields.Many2one('utility.contract.template', string='قالب العقد')
    amount = fields.Monetary(string='المبلغ')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    kwh = fields.Float(string='كيلوواط ساعة')
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
    ], default='pending', string='الحالة', tracking=True)
    retry_count = fields.Integer(string='عدد إعادة المحاولة', default=0)
    last_retry_date = fields.Datetime(string='تاريخ آخر محاولة')
    raw_request = fields.Text(string='الطلب الخام')
    raw_response = fields.Text(string='الرد الخام')
    sts_server = fields.Char(string='خادم STS')

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
        order_ref = self.pos_order_id.name or str(self.pos_order_id.id)
        _logger.info('Simulating STS token request for order %s', order_ref)
        dummy_token = ''.join([str((i * 7) % 10) for i in range(20)])
        meter_ref = self.meter_id.meter_number or self.meter_id.display_name or ''
        self.write({
            'token_number': dummy_token,
            'token_identifier': 'TID-%s-%s' % (order_ref, fields.Datetime.now().strftime('%Y%m%d%H%M%S')),
            'sequence_number': self.retry_count + 1,
            'response_date': fields.Datetime.now(),
            'response_code': '00',
            'response_message': _('تم إنشاء الرمز بنجاح'),
            'status': 'success',
            'raw_request': 'SIMULATED_REQUEST|amount=%s|kwh=%s|meter=%s' % (
                self.amount, self.kwh, meter_ref,
            ),
            'raw_response': 'SIMULATED_RESPONSE|token=%s|status=success' % dummy_token,
            'sts_server': 'SIMULATED',
        })

    def action_retry(self):
        self.ensure_one()
        self.write({
            'retry_count': self.retry_count + 1,
            'last_retry_date': fields.Datetime.now(),
            'status': 'retry',
        })
        self.action_request_token()

    def action_cancel(self):
        self.ensure_one()
        self.write({
            'status': 'cancelled',
            'response_date': fields.Datetime.now(),
            'response_message': _('تم إلغاء طلب الرمز بواسطة المشغل'),
        })
