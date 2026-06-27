from odoo import api, fields, models, _


class UtilityCollection(models.Model):
    _name = 'utility.collection'
    _description = 'Utility Collection'
    _order = 'payment_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    collection_number = fields.Char('Collection Number', default=lambda self: _('New'))
    customer_id = fields.Many2one('utility.customer', 'Customer')
    account_id = fields.Many2one('utility.customer', 'Account')
    bill_id = fields.Many2one('utility.bill', 'Bill')
    amount = fields.Float('Amount', required=True)
    payment_date = fields.Datetime('Payment Date', default=fields.Datetime.now)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('check', 'Check'),
        ('card', 'Card'),
        ('mobile', 'Mobile Money'),
    ], string='Payment Method', default='cash')
    reference_number = fields.Char('Reference Number')
    collected_by = fields.Many2one('res.users', 'Collected By')
    receipt_number = fields.Char('Receipt Number')
    notes = fields.Text('Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('collected', 'Collected'),
        ('verified', 'Verified'),
        ('reversed', 'Reversed'),
    ], string='State', default='draft')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('collection_number', _('New')) == _('New'):
                vals['collection_number'] = self.env['ir.sequence'].next_by_code('utility.collection') or _('New')
        return super().create(vals_list)
