from odoo import api, fields, models, _


class UtilityReadingSettlement(models.Model):
    _inherit = 'utility.reading.settlement'

    sale_order_id = fields.Many2one(
        'sale.order', 'Related Electricity Bill',
        compute='_compute_sale_order_id', store=True,
    )

    @api.depends('reading_id')
    def _compute_sale_order_id(self):
        for record in self:
            record.sale_order_id = False
            if record.reading_id:
                order = self.env['sale.order'].search([
                    ('reading_id', '=', record.reading_id.id),
                    ('state', '!=', 'cancel'),
                ], limit=1)
                record.sale_order_id = order.id if order else False

    def action_open_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Electricity Bill'),
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
