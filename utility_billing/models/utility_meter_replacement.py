from odoo import fields, models, _
from odoo.exceptions import UserError


class UtilityMeterReplacement(models.Model):
    _inherit = 'utility.meter.replacement'

    sale_order_id = fields.Many2one(
        'sale.order', string='فاتورة الاستهلاك المركبة',
        related='closing_reading_id.included_sale_order_id',
        store=True, readonly=True,
    )

    def action_view_sale_order(self):
        """Open the postpaid order containing the replacement consumption."""
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('لم يتم إدراج الاستهلاك غير المفوتر في فاتورة بعد.'))
        return {
            'name': _('فاتورة الاستهلاك المركبة'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
