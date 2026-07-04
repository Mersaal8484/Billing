from odoo import api, fields, models


class UtilityInventoryCountLine(models.Model):
    _name = 'utility.inventory.count.line'
    _description = 'بند جرد مخزون'
    _rec_name = 'item_id'
    _order = 'id'

    count_id = fields.Many2one('utility.inventory.count', 'الجرد', required=True, ondelete='cascade')
    item_id = fields.Many2one('utility.inventory.item', 'الصنف', required=True, ondelete='restrict')
    expected_quantity = fields.Float('الكمية المتوقعة', required=True, default=0.0)
    counted_quantity = fields.Float('الكمية الفعلية', required=True, default=0.0)
    difference = fields.Float('الفرق', compute='_compute_difference', store=True)
    notes = fields.Text('ملاحظات')

    @api.depends('expected_quantity', 'counted_quantity')
    def _compute_difference(self):
        for line in self:
            line.difference = line.counted_quantity - line.expected_quantity
