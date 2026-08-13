from odoo import fields, models, api


class StockWarehouseUtility(models.Model):
    _inherit = 'stock.warehouse'

    meter_inspection_location_id = fields.Many2one(
        'stock.location', string='موقع فحص العدادات',
        domain="[('usage', '=', 'internal')]",
        help='موقع فحص العدادات المسترجعة لهذا المستودع'
    )

    @api.model_create_multi
    def create(self, vals_list):
        warehouses = super().create(vals_list)
        for wh in warehouses:
            wh._ensure_meter_inspection_location()
        return warehouses

    def _ensure_meter_inspection_location(self):
        for wh in self:
            if not wh.meter_inspection_location_id:
                parent_loc = wh.view_location_id or wh.lot_stock_id.location_id
                loc = self.env['stock.location'].search([
                    ('name', 'ilike', f'فحص العدادات ({wh.code})'),
                    ('company_id', '=', wh.company_id.id),
                ], limit=1)
                if not loc:
                    loc = self.env['stock.location'].create({
                        'name': f'فحص العدادات ({wh.code})',
                        'usage': 'internal',
                        'location_id': parent_loc.id if parent_loc else False,
                        'company_id': wh.company_id.id,
                    })
                wh.meter_inspection_location_id = loc.id
        return True
