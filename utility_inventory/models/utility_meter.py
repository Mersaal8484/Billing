from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class UtilityMeter(models.Model):
    _inherit = 'utility.meter'

    product_id = fields.Many2one(
        'product.product', 
        string='المنتج (نوع العداد)',
        domain="[('tracking', '=', 'serial')]",
        help='المنتج المخزني الذي يمثل نوع هذا العداد'
    )
    lot_id = fields.Many2one(
        'stock.lot', 
        string='الرقم التسلسلي المخزني',
        domain="[('product_id', '=', product_id)]",
        help='السيريال نمبر من نظام المخازن'
    )
    condition = fields.Selection([
        ('new', 'جديد'),
        ('used', 'مستعمل/مُجدد'),
        ('faulty', 'معطل/بانتظار الفحص'),
        ('scrapped', 'تالف/سُكراب'),
    ], string='حالة العداد (Condition)', default='new', tracking=True)

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        if self.lot_id:
            if not self.serial_number or self.serial_number != self.lot_id.name:
                self.serial_number = self.lot_id.name
            if not self.meter_number:
                self.meter_number = self.lot_id.name
