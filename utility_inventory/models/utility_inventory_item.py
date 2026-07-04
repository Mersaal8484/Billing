from odoo import api, fields, models


class UtilityInventoryItem(models.Model):
    _name = 'utility.inventory.item'
    _description = 'صنف مخزون'
    _rec_name = 'name'
    _order = 'code, name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم الصنف', required=True, translate=True)
    code = fields.Char('كود الصنف', required=True)
    product_id = fields.Many2one('product.product', 'المنتج', required=True, ondelete='restrict')
    meter_id = fields.Many2one('utility.meter', 'العداد', ondelete='set null')
    lot_id = fields.Many2one('stock.lot', 'الرقم التسلسلي (Serial/Lot)', ondelete='restrict',
                             domain="[('product_id', '=', product_id)]",
                             help='الرقم التسلسلي للمنتجات المقتفاة بالأرقام التسلسلية')
    location_id = fields.Many2one('utility.inventory.location', 'موقع التخزين', required=True, ondelete='restrict')
    quantity = fields.Float('الكمية الحالية', required=True, default=0.0)
    min_quantity = fields.Float('الحد الأدنى للكمية', default=0.0)
    unit_price = fields.Monetary('سعر الوحدة', currency_field='company_currency_id')
    total_value = fields.Monetary('القيمة الإجمالية', currency_field='company_currency_id',
                                  compute='_compute_total_value', store=True)
    notes = fields.Text('ملاحظات')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='العملة')

    _sql_constraints = [
        ('unique_code_company', 'unique(code, company_id)',
         'كود الصنف يجب أن يكون فريداً لكل شركة!'),
    ]

    @api.depends('quantity', 'unit_price')
    def _compute_total_value(self):
        for item in self:
            item.total_value = item.quantity * item.unit_price
