from odoo import fields, models, api


class StockWarehouseUtility(models.Model):
    _inherit = 'stock.warehouse'

    meter_inspection_location_id = fields.Many2one(
        'stock.location', string='موقع فحص العدادات',
        domain="[('usage', '=', 'internal')]",
        help='موقع فحص العدادات المسترجعة لهذا المستودع'
    )
    meter_repair_location_id = fields.Many2one(
        'stock.location', string='موقع صيانة العدادات',
        domain="[('usage', '=', 'internal')]",
        help='موقع صيانة وإصلاح العدادات لهذا المستودع'
    )

    @api.model_create_multi
    def create(self, vals_list):
        warehouses = super().create(vals_list)
        for wh in warehouses:
            wh._ensure_utility_meter_locations()
        return warehouses

    def _ensure_utility_meter_locations(self):
        for wh in self:
            parent_loc = wh.view_location_id or wh.lot_stock_id.location_id
            
            # 1. Inspection Location
            if not wh.meter_inspection_location_id:
                loc_insp = self.env['stock.location'].search([
                    ('name', 'ilike', f'فحص العدادات ({wh.code})'),
                    ('company_id', '=', wh.company_id.id),
                ], limit=1)
                if not loc_insp:
                    loc_insp = self.env['stock.location'].create({
                        'name': f'فحص العدادات ({wh.code})',
                        'usage': 'internal',
                        'location_id': parent_loc.id if parent_loc else False,
                        'company_id': wh.company_id.id,
                    })
                wh.meter_inspection_location_id = loc_insp.id

            # 2. Repair Location
            if not wh.meter_repair_location_id:
                loc_rep = self.env['stock.location'].search([
                    ('name', 'ilike', f'صيانة العدادات ({wh.code})'),
                    ('company_id', '=', wh.company_id.id),
                ], limit=1)
                if not loc_rep:
                    loc_rep = self.env['stock.location'].create({
                        'name': f'صيانة العدادات ({wh.code})',
                        'usage': 'internal',
                        'location_id': parent_loc.id if parent_loc else False,
                        'company_id': wh.company_id.id,
                    })
                wh.meter_repair_location_id = loc_rep.id
        return True
