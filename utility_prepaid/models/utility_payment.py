from odoo import api, fields, models, _


class UtilityPayment(models.Model):
    _name = 'utility.payment'
    _inherit = ['mail.thread']

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    payment_reference = fields.Char(required=True, default=lambda self: _('New'))
    payment_date = fields.Datetime(default=fields.Datetime.now)
    sale_id = fields.Many2one('utility.sale', string='Sale')
    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    account_id = fields.Many2one('utility.customer', string='Account', required=True)
    amount = fields.Monetary(string='Amount', required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('pos', 'POS Terminal'),
        ('bank', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('wallet', 'Digital Wallet'),
        ('online', 'Online Payment'),
    ], string='Payment Method')
    reference_number = fields.Char(string='Reference Number')
    bank_name = fields.Char(string='Bank Name')
    check_number = fields.Char(string='Check Number')
    mobile_provider = fields.Char(string='Mobile Provider')
    wallet_provider = fields.Char(string='Wallet Provider')
    online_gateway = fields.Char(string='Online Gateway')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('reconciled', 'Reconciled'),
        ('reversed', 'Reversed'),
        ('failed', 'Failed'),
    ], default='draft', string='State', tracking=True)
    operator_id = fields.Many2one('res.users', string='Operator', default=lambda self: self.env.user)
    notes = fields.Text(string='Notes')
    reversal_id = fields.Many2one('utility.reversal', string='Reversal')

    @api.model
    def create(self, vals):
        if vals.get('payment_reference', _('New')) == _('New'):
            vals['payment_reference'] = self.env['ir.sequence'].next_by_code('utility.payment') or _('New')
        return super(UtilityPayment, self).create(vals)
