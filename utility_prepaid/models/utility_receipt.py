from odoo import api, fields, models, _


class UtilityReceipt(models.Model):
    _name = 'utility.receipt'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    receipt_number = fields.Char(required=True, default=lambda self: _('New'))
    sale_id = fields.Many2one('utility.sale', string='Sale', required=True)
    customer_id = fields.Many2one('res.partner', related='sale_id.customer_id', string='Customer', store=True)
    account_id = fields.Many2one('utility.customer', related='sale_id.account_id', string='Account', store=True)
    meter_id = fields.Many2one('utility.meter', related='sale_id.meter_id', string='Meter', store=True)
    amount = fields.Monetary(related='sale_id.amount_paid', string='Amount')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    kwh = fields.Float(related='sale_id.kwh_purchased', string='kWh')
    token_id = fields.Many2one('utility.token', related='sale_id.token_id', string='Token', store=True)
    payment_method = fields.Selection(related='sale_id.payment_method', string='Payment Method')
    receipt_date = fields.Datetime(default=fields.Datetime.now, string='Receipt Date')
    operator_id = fields.Many2one('res.users', related='sale_id.operator_id', string='Operator', store=True)
    printed = fields.Boolean(string='Printed')
    sms_sent = fields.Boolean(string='SMS Sent')

    @api.model
    def create(self, vals):
        if vals.get('receipt_number', _('New')) == _('New'):
            vals['receipt_number'] = self.env['ir.sequence'].next_by_code('utility.receipt') or _('New')
        return super(UtilityReceipt, self).create(vals)
