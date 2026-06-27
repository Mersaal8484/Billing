import logging
from datetime import datetime

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class UtilityToken(models.Model):
    _name = 'utility.token'
    _inherit = ['mail.thread']

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    token_number = fields.Char(string='Token Number', index=True)
    token_identifier = fields.Char(string='Token Identifier (TID)')
    sequence_number = fields.Integer(string='Sequence Number')
    sale_id = fields.Many2one('utility.sale', string='Sale', required=True, ondelete='cascade')
    account_id = fields.Many2one('utility.customer', string='Account', required=True)
    meter_id = fields.Many2one('utility.meter', string='Meter', required=True)
    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    tariff_id = fields.Many2one('utility.tariff', string='Tariff')
    amount = fields.Monetary(string='Amount')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    kwh = fields.Float(string='kWh')
    request_date = fields.Datetime(default=fields.Datetime.now, string='Request Date')
    response_date = fields.Datetime(string='Response Date')
    response_code = fields.Char(string='Response Code')
    response_message = fields.Text(string='Response Message')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('retry', 'Retry'),
        ('cancelled', 'Cancelled'),
    ], default='pending', string='Status', tracking=True)
    retry_count = fields.Integer(string='Retry Count', default=0)
    last_retry_date = fields.Datetime(string='Last Retry Date')
    raw_request = fields.Text(string='Raw Request')
    raw_response = fields.Text(string='Raw Response')
    sts_server = fields.Char(string='STS Server')

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
        _logger.info('Simulating STS token request for sale %s', self.sale_id.receipt_number)
        dummy_token = ''.join([str((i * 7) % 10) for i in range(20)])
        self.write({
            'token_number': dummy_token,
            'token_identifier': 'TID-%s-%s' % (self.sale_id.id, fields.Datetime.now().strftime('%Y%m%d%H%M%S')),
            'sequence_number': self.retry_count + 1,
            'response_date': fields.Datetime.now(),
            'response_code': '00',
            'response_message': _('Token generated successfully'),
            'status': 'success',
            'raw_request': 'SIMULATED_REQUEST|amount=%s|kwh=%s|meter=%s' % (
                self.amount, self.kwh, self.meter_id.name if self.meter_id else '',
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
            'response_message': _('Token request cancelled by operator'),
        })
