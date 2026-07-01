from odoo import api, fields, models, _

class UtilityRegion(models.Model):
    _inherit = 'utility.region'

    location_id = fields.Many2one(
        'stock.location', 
        string='الموقع المخزني',
        help='الموقع المخزني المرتبط بهذه المنطقة لصرف العدادات والمواد'
    )

    @api.model_create_multi
    def create(self, vals_list):
        # Create regions
        regions = super(UtilityRegion, self).create(vals_list)
        
        # Auto-create stock locations for regions that don't have one
        # We place them under the main company's stock location
        for region in regions:
            if not region.location_id:
                company_location = self.env['stock.warehouse'].search([('company_id', '=', region.company_id.id)], limit=1).lot_stock_id
                
                parent_location_id = company_location.id if company_location else self.env.ref('stock.stock_location_stock').id
                
                # If region has a parent with a location, use that as parent
                if region.parent_id and region.parent_id.location_id:
                    parent_location_id = region.parent_id.location_id.id
                
                loc = self.env['stock.location'].create({
                    'name': region.name,
                    'location_id': parent_location_id,
                    'usage': 'internal',
                    'company_id': region.company_id.id,
                })
                region.location_id = loc.id
                
        return regions
