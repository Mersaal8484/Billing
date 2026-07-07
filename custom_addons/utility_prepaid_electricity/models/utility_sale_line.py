from odoo import api, fields, models


class UtilitySaleLine(models.Model):
    _name = 'utility.sale.line'
    _description = 'Sale Line Item'
    _order = 'sale_id, sequence'

    sale_id = fields.Many2one('utility.sale', string='Sale', required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Description', required=True)
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    unit = fields.Char(string='Unit', default='kWh')
    unit_price = fields.Monetary(string='Unit Price', digits=(16, 6), required=True)
    subtotal = fields.Monetary(string='Subtotal', digits=(16, 4), compute='_compute_subtotal', store=True)
    currency_id = fields.Many2one('res.currency', related='sale_id.currency_id')

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.quantity * rec.unit_price
