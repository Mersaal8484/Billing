from odoo import api, fields, models, _


class UtilityDeposit(models.Model):
    _name = 'utility.deposit'
    _description = 'Utility Deposit'
    _order = 'deposit_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    deposit_number = fields.Char('Deposit Number', required=True, default=lambda self: _('New'))
    customer_id = fields.Many2one('utility.customer', 'Customer')
    account_id = fields.Many2one('utility.customer', 'Account')
    meter_id = fields.Many2one('utility.meter', 'Meter')
    amount = fields.Float('Amount')
    deposit_date = fields.Date('Deposit Date')
    deposit_type = fields.Selection([
        ('connection', 'Connection'),
        ('security', 'Security'),
        ('meter', 'Meter'),
    ], string='Deposit Type', default='security')
    status = fields.Selection([
        ('held', 'Held'),
        ('released', 'Released'),
        ('forfeited', 'Forfeited'),
    ], string='Status', default='held')
    release_date = fields.Date('Release Date')
    notes = fields.Text('Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('deposit_number', _('New')) == _('New'):
                vals['deposit_number'] = self.env['ir.sequence'].next_by_code('utility.deposit') or _('New')
        return super().create(vals_list)
