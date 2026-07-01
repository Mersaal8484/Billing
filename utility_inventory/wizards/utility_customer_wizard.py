from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class UtilityCustomerWizard(models.TransientModel):
    _inherit = 'utility.customer.wizard'

    product_id = fields.Many2one(
        'product.product', 
        string='نوع العداد (المخزن)',
        domain="[('tracking', '=', 'serial')]",
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='الرقم التسلسلي (المخزن)',
        domain="[('product_id', '=', product_id), ('quant_ids.quantity', '>', 0)]",
    )
    lot_condition = fields.Char(string='حالة العداد المخزني', compute='_compute_lot_condition')

    @api.depends('lot_id')
    def _compute_lot_condition(self):
        for rec in self:
            if rec.lot_id:
                meter = self.env['utility.meter'].search([('lot_id', '=', rec.lot_id.id)], limit=1)
                if meter:
                    condition_dict = dict(meter._fields['condition'].selection)
                    rec.lot_condition = condition_dict.get(meter.condition, 'غير معروف')
                else:
                    rec.lot_condition = 'جديد (لم يستخدم من قبل)'
            else:
                rec.lot_condition = False

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        if self.lot_id:
            self.meter_number = self.lot_id.name
            self.serial_number = self.lot_id.name

    def action_create_customer(self):
        # Run original wizard logic
        res = super(UtilityCustomerWizard, self).action_create_customer()
        
        customer_id = res.get('res_id')
        if customer_id and self.lot_id:
            customer = self.env['utility.customer'].browse(customer_id)
            # Find the meter created by the wizard
            meter = self.env['utility.meter'].search([('customer_id', '=', customer_id)], limit=1)
            
            if meter:
                # Update meter with stock info
                meter.write({
                    'product_id': self.product_id.id,
                    'lot_id': self.lot_id.id,
                })
                
                # Auto-generate and validate delivery order
                self._create_meter_delivery(customer, meter)
                
        return res

    def _create_meter_delivery(self, customer, meter):
        # Source location: the region's location, or the main stock if region has no location
        src_location_id = False
        if customer.area_id and customer.area_id.location_id:
            src_location_id = customer.area_id.location_id.id
        elif customer.region_id and customer.region_id.location_id:
            src_location_id = customer.region_id.location_id.id
        else:
            # Fallback to main company stock
            wh = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
            if wh:
                src_location_id = wh.lot_stock_id.id

        # Destination location: Customer Location
        dest_location = self.env.ref('utility_inventory.stock_location_utility_customers', raise_if_not_found=False)
        dest_location_id = dest_location.id if dest_location else self.env.ref('stock.stock_location_customers').id
        
        if not src_location_id:
            return # Cannot create delivery if no source location is found
            
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)

        picking = self.env['stock.picking'].create({
            'partner_id': customer.partner_id.id,
            'picking_type_id': picking_type.id if picking_type else False,
            'location_id': src_location_id,
            'location_dest_id': dest_location_id,
            'origin': f'صرف عداد للمشترك: {customer.customer_number}',
        })

        move = self.env['stock.move'].create({
            'name': f'صرف العداد {meter.meter_number}',
            'product_id': self.product_id.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_id.uom_id.id,
            'picking_id': picking.id,
            'location_id': src_location_id,
            'location_dest_id': dest_location_id,
        })
        
        # Confirm and assign the specific lot
        picking.action_confirm()
        
        move_line = self.env['stock.move.line'].create({
            'move_id': move.id,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_id.uom_id.id,
            'qty_done': 1.0,
            'lot_id': self.lot_id.id,
            'picking_id': picking.id,
            'location_id': src_location_id,
            'location_dest_id': dest_location_id,
        })
        
        picking.button_validate()
