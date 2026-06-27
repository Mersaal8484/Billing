from odoo import api, fields, models, _


class UtilityWriteoff(models.Model):
    _name = 'utility.writeoff'
    _description = 'Utility Writeoff'
    _order = 'date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    writeoff_number = fields.Char('Writeoff Number', required=True, default=lambda self: _('New'))
    customer_id = fields.Many2one('utility.customer', 'Customer')
    account_id = fields.Many2one('utility.customer', 'Account')
    sale_order_id = fields.Many2one('sale.order', 'Sale Order')
    amount = fields.Float('Amount')
    reason = fields.Text('Reason')
    approved_by = fields.Many2one('res.users', 'Approved By')
    date = fields.Datetime('Date', default=fields.Datetime.now)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('applied', 'Applied'),
    ], string='State', default='draft')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('writeoff_number', _('New')) == _('New'):
                vals['writeoff_number'] = self.env['ir.sequence'].next_by_code('utility.writeoff') or _('New')
        return super().create(vals_list)
