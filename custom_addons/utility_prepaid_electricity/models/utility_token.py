from odoo import api, fields, models, _
from odoo.exceptions import UserError
import time


class UtilityToken(models.Model):
    _name = 'utility.token'
    _description = 'STS Token'
    _order = 'create_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)

    token_number = fields.Char(string='Token Number', index=True, copy=False,
                               help='20-digit STS token')
    token_identifier = fields.Char(string='Token Identifier (TID)', index=True, copy=False)
    sequence_number = fields.Integer(string='Sequence Number', index=True, copy=False)

    sale_id = fields.Many2one('utility.sale', string='Sale', required=True, index=True, ondelete='cascade')
    account_id = fields.Many2one('utility.account', string='Account', required=True, index=True)
    meter_id = fields.Many2one('utility.meter', string='Meter', required=True, index=True)
    customer_id = fields.Many2one('utility.customer', string='Customer', required=True, index=True)
    tariff_id = fields.Many2one('utility.tariff', string='Tariff', index=True)

    amount = fields.Monetary(string='Amount', required=True, digits=(16, 4))
    kwh = fields.Float(string='kWh Purchased', digits=(16, 2), required=True)

    request_date = fields.Datetime(string='Request Date', default=fields.Datetime.now)
    response_date = fields.Datetime(string='Response Date')
    response_code = fields.Char(string='Response Code')
    response_message = fields.Text(string='Response Message')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('retry', 'Retry'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='pending', index=True, tracking=True, required=True)

    retry_count = fields.Integer(string='Retry Count', default=0)
    last_retry_date = fields.Datetime(string='Last Retry Date')

    raw_request = fields.Text(string='Raw Request')
    raw_response = fields.Text(string='Raw Response')
    sts_server = fields.Char(string='STS Server')

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    _sql_constraints = [
        ('token_uniq', 'UNIQUE(token_number, company_id)', 'Token number must be unique!'),
    ]

    def action_request_token(self):
        """
        Pluggable STS token generation.
        In production, this calls an external STS vending server.
        Override this method or use the integration hook.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        # Simulated STS integration - in production, replace with real STS API call
        # ==================== STS INTEGRATION POINT ====================
        # Call external vending server API here
        # token_response = sts_vending_api.generate_token(
        #     meter_no=self.meter_id.meter_number,
        #     amount=self.amount,
        #     kwh=self.kwh,
        #     tariff_code=self.tariff_id.code if self.tariff_id else '',
        #     key_revision=self.meter_id.sts_key_revision,
        # )
        # ==============================================================
        simulated_token = str(int(time.time()))[-10:].zfill(10)
        simulated_token += str(self.id).zfill(10)
        self.write({
            'token_number': simulated_token,
            'token_identifier': f'TID-{self.id}',
            'sequence_number': self.id,
            'response_date': now,
            'status': 'success',
            'response_code': '00',
            'response_message': 'Token generated successfully',
        })
        return True

    def action_retry(self):
        if self.retry_count >= 3:
            raise UserError(_('Maximum retry attempts reached. Please create a new token request.'))
        self.write({
            'retry_count': self.retry_count + 1,
            'last_retry_date': fields.Datetime.now(),
            'status': 'retry',
        })
        return self.action_request_token()

    def action_cancel(self):
        self.write({'status': 'cancelled'})
