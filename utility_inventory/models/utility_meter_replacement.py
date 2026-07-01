from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class UtilityMeterReplacement(models.Model):
    _inherit = 'utility.meter.replacement'

    def action_confirm_replacement(self):
        # We need to capture old meter before it's processed/deactivated
        old_meters = {rec.id: rec.old_meter_id for rec in self if rec.old_meter_id}
        
        res = super(UtilityMeterReplacement, self).action_confirm_replacement()
        
        for rec in self:
            old_meter = old_meters.get(rec.id)
            new_meter = rec.new_meter_id
            
            customer = rec.utility_account_id
            
            # Determine region location
            region_location_id = False
            if customer.area_id and customer.area_id.location_id:
                region_location_id = customer.area_id.location_id.id
            elif customer.region_id and customer.region_id.location_id:
                region_location_id = customer.region_id.location_id.id
            else:
                wh = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
                if wh:
                    region_location_id = wh.lot_stock_id.id
                    
            customer_location = self.env.ref('utility_inventory.stock_location_utility_customers', raise_if_not_found=False)
            customer_location_id = customer_location.id if customer_location else self.env.ref('stock.stock_location_customers').id
            
            if not region_location_id:
                continue

            # 1. Return Old Meter
            if old_meter and old_meter.lot_id:
                # Re-activate meter so it can be seen in inventory/repairs
                old_meter.write({
                    'condition': 'faulty', 
                    'active': True,
                    'customer_id': False # Ensure it's unlinked from customer
                })
                self._create_transfer(
                    customer.partner_id.id,
                    old_meter,
                    src_location_id=customer_location_id,
                    dest_location_id=region_location_id,
                    origin=f'مرتجع استبدال عداد: {customer.customer_number}',
                    picking_type_code='incoming'
                )

            # 2. Deliver New Meter (if lot_id exists)
            if new_meter and new_meter.lot_id:
                self._create_transfer(
                    customer.partner_id.id,
                    new_meter,
                    src_location_id=region_location_id,
                    dest_location_id=customer_location_id,
                    origin=f'صرف عداد بديل: {customer.customer_number}',
                    picking_type_code='outgoing'
                )
                
        return res

    def _create_transfer(self, partner_id, meter, src_location_id, dest_location_id, origin, picking_type_code):
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', picking_type_code),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)

        picking = self.env['stock.picking'].create({
            'partner_id': partner_id,
            'picking_type_id': picking_type.id if picking_type else False,
            'location_id': src_location_id,
            'location_dest_id': dest_location_id,
            'origin': origin,
        })

        move = self.env['stock.move'].create({
            'name': meter.meter_number,
            'product_id': meter.product_id.id,
            'product_uom_qty': 1.0,
            'product_uom': meter.product_id.uom_id.id,
            'picking_id': picking.id,
            'location_id': src_location_id,
            'location_dest_id': dest_location_id,
        })
        
        picking.action_confirm()
        
        self.env['stock.move.line'].create({
            'move_id': move.id,
            'product_id': meter.product_id.id,
            'product_uom_id': meter.product_id.uom_id.id,
            'qty_done': 1.0,
            'lot_id': meter.lot_id.id,
            'picking_id': picking.id,
            'location_id': src_location_id,
            'location_dest_id': dest_location_id,
        })
        
        picking.button_validate()
