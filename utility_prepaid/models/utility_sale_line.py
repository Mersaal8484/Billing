from odoo import api, fields, models


class UtilitySaleLine(models.Model):
    _name = 'utility.sale.line'

    sale_id = fields.Many2one('utility.sale', string='Sale', required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0)
    unit = fields.Char(string='Unit')
    unit_price = fields.Float(string='Unit Price')
    subtotal = fields.Monetary(compute='_compute_subtotal', string='Subtotal', store=True)
    currency_id = fields.Many2one('res.currency', related='sale_id.currency_id')

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = (line.quantity or 0.0) * (line.unit_price or 0.0)
