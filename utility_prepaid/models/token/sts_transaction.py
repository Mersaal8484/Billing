import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UtilityStsTransaction(models.Model):
    _name = 'utility.sts.transaction'
    _description = 'معاملة STS'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company, index=True)
    reference = fields.Char('المرجع', required=True, copy=False, index=True, default=lambda self: _('جديد'))
    idempotency_key = fields.Char('مفتاح منع التكرار', index=True, copy=False)

    vending_request_id = fields.Many2one('utility.vending.request', 'طلب البيع',
        index=True, ondelete='set null')
    token_id = fields.Many2one('utility.token', 'التوكن', index=True, ondelete='set null')
    reversal_id = fields.Many2one('utility.vending.reversal', 'العكس', index=True)

    provider_id = fields.Many2one('utility.sts.provider', 'مزود STS', required=True, index=True)
    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, index=True)
    account_id = fields.Many2one('utility.customer', 'الحساب', index=True)

    transaction_type = fields.Selection([
        ('credit', 'رصيد'),
        ('management', 'إدارة'),
        ('key_change', 'تغيير المفتاح'),
        ('reverse', 'عكس'),
        ('query', 'استعلام'),
    ], 'نوع المعاملة', default='credit', required=True)

    amount = fields.Monetary('المبلغ', currency_field='currency_id')
    kwh = fields.Float('الكيلوواط ساعة', digits=(12, 3))
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)

    token_value = fields.Char('قيمة التوكن', readonly=True)
    token_identifier = fields.Char('معرف التوكن', readonly=True)
    provider_reference = fields.Char('مرجع المزود', index=True, readonly=True)

    state = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('sent', 'مُرسل'),
        ('success', 'ناجح'),
        ('failed', 'فشل'),
        ('reversed', 'مَعكوس'),
        ('cancelled', 'ملغى'),
    ], 'الحالة', default='pending', tracking=True, index=True)

    retry_count = fields.Integer('عدد إعادة المحاولة', default=0)
    error_code = fields.Char('رمز الخطأ')
    error_message = fields.Text('رسالة الخطأ')
    raw_request = fields.Text('الطلب الخام')
    raw_response = fields.Text('الرد الخام')

    request_date = fields.Datetime('تاريخ الطلب')
    response_date = fields.Datetime('تاريخ الرد')

    _sql_constraints = [
        ('sts_ref_provider_unique',
         'unique(provider_id, provider_reference)',
         'مرجع المزود يجب أن يكون فريداً لكل مزود.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('جديد')) == _('جديد'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('utility.sts.transaction') or _('جديد')
        return super().create(vals_list)

    def action_send_request(self):
        for rec in self:
            if rec.state not in ('pending', 'failed'):
                raise UserError(_('يمكن إرسال الطلب فقط من حالة الانتظار أو الفشل.'))

            rec.write({
                'request_date': fields.Datetime.now(),
                'retry_count': rec.retry_count + 1,
                'state': 'sent',
            })

            try:
                result = rec.provider_id.send_generate_token(
                    meter_number=rec.meter_id.meter_number,
                    amount=rec.amount,
                    kwh=rec.kwh,
                    token_type=rec.transaction_type,
                )
                rec._process_sts_response(result)
            except Exception as e:
                _logger.exception('STS transaction %s failed', rec.reference)
                rec.write({
                    'state': 'failed',
                    'error_code': 'ERROR',
                    'error_message': str(e),
                    'response_date': fields.Datetime.now(),
                    'raw_response': str(e),
                })

    def _process_sts_response(self, result):
        self.ensure_one()
        if result.get('success'):
            self.write({
                'state': 'success',
                'token_value': result.get('token_value'),
                'token_identifier': result.get('token_identifier'),
                'provider_reference': result.get('provider_reference'),
                'raw_response': result.get('raw_response', ''),
                'response_code': result.get('response_code', '00'),
                'response_date': fields.Datetime.now(),
                'error_code': False,
                'error_message': False,
            })
            if self.token_id:
                self.token_id.write({
                    'token_number': result.get('token_value'),
                    'token_identifier': result.get('token_identifier'),
                    'status': 'success',
                    'provider_reference': result.get('provider_reference'),
                    'response_date': fields.Datetime.now(),
                    'response_code': result.get('response_code', '00'),
                    'response_message': _('تم إنشاء الرمز بنجاح'),
                })
        else:
            self.write({
                'state': 'failed',
                'error_code': result.get('error_code', 'UNKNOWN'),
                'error_message': result.get('error_message', _('فشل غير معروف')),
                'raw_response': result.get('raw_response', ''),
                'response_date': fields.Datetime.now(),
            })
            if self.token_id:
                self.token_id.write({
                    'status': 'failed',
                    'response_date': fields.Datetime.now(),
                    'response_code': result.get('error_code', 'ERROR'),
                    'response_message': result.get('error_message', ''),
                })

    def action_query_status(self):
        self.ensure_one()
        if not self.provider_reference:
            raise UserError(_('لا يوجد مرجع مزود للاستعلام عنه.'))
        result = self.provider_id.send_query_transaction(self.provider_reference)
        if result.get('success'):
            if result.get('state') == 'success' and not self.token_value:
                _logger.info('Pending transaction %s found as success by provider', self.reference)

    def action_reverse(self):
        self.ensure_one()
        if self.state != 'success':
            raise UserError(_('يمكن عكس المعاملات الناجحة فقط.'))
        result = self.provider_id.send_reverse_transaction(
            token_value=self.token_value,
            meter_number=self.meter_id.meter_number,
        )
        if result.get('success'):
            self.state = 'reversed'
            self.raw_response = (self.raw_response or '') + '\nREVERSED: ' + result.get('raw_response', '')
        else:
            raise UserError(_('فشل عكس المعاملة: %s') % result.get('error_message', ''))

    @api.model
    def _cron_retry_failed_sts(self):
        failed = self.search([
            ('state', '=', 'failed'),
            ('retry_count', '<', self.env.company.sts_max_retry_count or 3),
        ], limit=50)
        for tx in failed:
            try:
                tx.action_send_request()
            except Exception:
                _logger.exception('Cron retry failed for STS transaction %s', tx.reference)

    @api.model
    def _cron_query_pending(self):
        pending = self.search([
            ('state', '=', 'pending'),
            ('request_date', '<=', fields.Datetime.now()),
            ('provider_reference', '!=', False),
        ], limit=100)
        for tx in pending:
            try:
                tx.action_query_status()
            except Exception:
                _logger.exception('Cron query failed for STS transaction %s', tx.reference)

    @api.model
    def _cron_monitor_health(self):
        providers = self.env['utility.sts.provider'].search([('active', '=', True)])
        for provider in providers:
            try:
                provider.action_health_check()
            except Exception:
                _logger.exception('Health check failed for provider %s', provider.name)
