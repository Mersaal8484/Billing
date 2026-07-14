import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UtilityStsProvider(models.Model):
    _name = 'utility.sts.provider'
    _description = 'مزود خدمة STS'
    _order = 'sequence, name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم المزود', required=True)
    code = fields.Char('رمز المزود', required=True, index=True)
    sequence = fields.Integer('التسلسل', default=10)

    provider_type = fields.Selection([
        ('generic_rest', 'Generic REST'),
        ('generic_soap', 'Generic SOAP'),
        ('hexing', 'Hexing'),
        ('inhemeter', 'Inhemeter'),
        ('landis_gyr', 'Landis+Gyr'),
        ('conlog', 'Conlog'),
        ('custom', 'Custom Provider'),
        ('simulated', 'محاكاة (اختبار)'),
    ], 'نوع المزود', required=True, default='simulated')

    base_url = fields.Char('رابط الخادم')
    api_key = fields.Char('مفتاح API')
    api_secret = fields.Char('سر API')
    timeout = fields.Integer('مهلة الطلب (ثانية)', default=30)
    max_retries = fields.Integer('أقصى إعادة محاولة', default=3)
    retry_interval = fields.Integer('فاصل إعادة المحاولة (ثانية)', default=5)

    is_default = fields.Boolean('افتراضي', default=False,
        help='هل هذا المزود هو المزود الافتراضي للشركة؟')

    health_state = fields.Selection([
        ('healthy', 'سليم'),
        ('degraded', 'متدهور'),
        ('down', 'متوقف'),
        ('unknown', 'غير معروف'),
    ], 'حالة المزود', default='unknown')
    last_health_check = fields.Datetime('آخر فحص')
    last_error = fields.Text('آخر خطأ')

    config_json = fields.Text('إعدادات إضافية (JSON)')
    description = fields.Text('الوصف')

    _sql_constraints = [
        ('code_unique', 'unique(code, company_id)', 'رمز المزود يجب أن يكون فريداً لكل شركة.'),
    ]

    def action_health_check(self):
        for rec in self:
            try:
                if rec.provider_type == 'simulated':
                    rec.write({
                        'health_state': 'healthy',
                        'last_health_check': fields.Datetime.now(),
                        'last_error': False,
                    })
                else:
                    rec.write({
                        'health_state': 'unknown',
                        'last_health_check': fields.Datetime.now(),
                    })
                    _logger.info('Health check initiated for provider %s', rec.name)
            except Exception as e:
                rec.write({
                    'health_state': 'down',
                    'last_health_check': fields.Datetime.now(),
                    'last_error': str(e),
                })
                _logger.exception('Health check failed for provider %s', rec.name)

    def send_generate_token(self, meter_number, amount, kwh, token_type='credit', extra=None):
        self.ensure_one()
        if self.provider_type == 'simulated':
            import hashlib
            import time
            raw = f'{meter_number}{amount}{kwh}{time.time()}'
            dummy_token = hashlib.md5(raw.encode()).hexdigest()[:20]
            dummy_token = ''.join([c if c.isdigit() else str(ord(c) % 10) for c in dummy_token])
            return {
                'success': True,
                'token_value': dummy_token,
                'token_identifier': 'TID-%s-%s' % (meter_number, int(time.time())),
                'provider_reference': 'SIM-%s' % int(time.time()),
                'raw_response': 'SIMULATED_SUCCESS',
                'response_code': '00',
            }
        elif self.provider_type == 'generic_rest':
            return self._send_rest_request(meter_number, amount, kwh, token_type, extra)
        else:
            raise UserError(
                _('نوع المزود "%s" غير مدعوم حالياً. استخدم واجهة STS Gateway المخصصة.')
                % self.provider_type
            )

    def _send_rest_request(self, meter_number, amount, kwh, token_type='credit', extra=None):
        import requests
        self.ensure_one()
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'

            payload = {
                'meter_number': meter_number,
                'amount': amount,
                'kwh': kwh,
                'token_type': token_type,
            }
            if extra:
                payload.update(extra)

            response = requests.post(
                f'{self.base_url}/generate_token',
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            return {
                'success': True,
                'token_value': data.get('token_value'),
                'token_identifier': data.get('token_identifier'),
                'provider_reference': data.get('provider_reference'),
                'raw_response': response.text,
                'response_code': data.get('response_code', '00'),
            }
        except requests.RequestException as e:
            _logger.exception('STS REST request failed for provider %s', self.name)
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'HTTP_ERROR',
                'raw_response': str(e),
            }

    def send_query_transaction(self, provider_reference):
        self.ensure_one()
        if self.provider_type == 'simulated':
            return {
                'success': True,
                'state': 'success',
                'raw_response': 'SIMULATED_QUERY',
            }
        raise NotImplementedError(_('استعلام المعاملات غير مُنفذ لهذا النوع من المزود.'))

    def send_reverse_transaction(self, token_value, meter_number):
        self.ensure_one()
        if self.provider_type == 'simulated':
            return {
                'success': True,
                'raw_response': 'SIMULATED_REVERSAL',
            }
        raise NotImplementedError(_('عكس المعاملات غير مُنفذ لهذا النوع من المزود.'))
