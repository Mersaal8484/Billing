import json
import logging

import requests

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class UtilityIntegrationProvider(models.Model):
    _name = 'utility.integration.provider'
    _description = 'مزود تكامل خارجي'
    _order = 'sequence, name'

    name = fields.Char('الاسم', required=True)
    sequence = fields.Integer('الترتيب', default=10)
    active = fields.Boolean('نشط', default=True)
    provider_type = fields.Selection([
        ('sms', 'رسائل قصيرة (SMS)'),
        ('ami', 'قراءة تلقائية (AMI)'),
        ('payment_gateway', 'بوابة دفع'),
    ], string='نوع المزود', required=True, index=True)
    mode = fields.Selection([
        ('manual', 'يدوي/تجريبي'),
        ('http_json', 'اتصال HTTP (JSON)'),
    ], string='وضع التكامل', default='manual', required=True)
    endpoint_url = fields.Char('Endpoint URL')
    api_key = fields.Char('API Key')
    webhook_secret = fields.Char('Webhook Secret')
    timeout = fields.Integer('مهلة الانتظار (ثواني)', default=15)
    last_error = fields.Text('آخر خطأ', readonly=True)

    def _build_headers(self):
        self.ensure_one()
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = 'Bearer %s' % self.api_key
        return headers

    def call_json(self, payload, event_type, record=None):
        self.ensure_one()
        log = self.env['utility.integration.log'].sudo().create({
            'provider_id': self.id,
            'event_type': event_type,
            'model_name': record._name if record else False,
            'res_id': record.id if record else False,
            'request_payload': json.dumps(payload, ensure_ascii=False, default=str),
            'state': 'pending',
        })
        if self.mode == 'manual':
            log.write({'state': 'success', 'response_payload': '{"mode": "manual"}'})
            return log
        if not self.endpoint_url:
            message = _('لم يتم ضبط رابط Endpoint للمزود %s.') % self.name
            log.write({'state': 'failed', 'error_message': message})
            self.last_error = message
            return log
        try:
            response = requests.post(
                self.endpoint_url,
                data=json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8'),
                headers=self._build_headers(),
                timeout=self.timeout or 15,
            )
            log.write({
                'http_status': response.status_code,
                'response_payload': response.text[:4000],
                'state': 'success' if 200 <= response.status_code < 300 else 'failed',
                'error_message': False if 200 <= response.status_code < 300 else response.text[:1000],
            })
            if not 200 <= response.status_code < 300:
                self.last_error = response.text[:1000]
        except Exception as exc:
            _logger.exception('Utility integration call failed')
            log.write({'state': 'failed', 'error_message': str(exc)})
            self.last_error = str(exc)
        return log


class UtilityIntegrationLog(models.Model):
    _name = 'utility.integration.log'
    _description = 'سجل التكاملات الخارجية'
    _order = 'create_date desc, id desc'

    provider_id = fields.Many2one('utility.integration.provider', string='المزود', required=True, ondelete='restrict')
    provider_type = fields.Selection(related='provider_id.provider_type', string='نوع المزود', store=True)
    event_type = fields.Char('نوع الحدث', required=True)
    model_name = fields.Char('النموذج')
    res_id = fields.Integer('معرف السجل')
    request_payload = fields.Text('الطلب')
    response_payload = fields.Text('الاستجابة')
    http_status = fields.Integer('حالة HTTP')
    state = fields.Selection([
        ('pending', 'قيد التنفيذ'),
        ('success', 'ناجح'),
        ('failed', 'فشل'),
    ], string='الحالة', default='pending', index=True)
    error_message = fields.Text('رسالة الخطأ')