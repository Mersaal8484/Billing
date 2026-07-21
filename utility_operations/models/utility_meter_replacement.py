from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMeterReplacement(models.Model):
    _inherit = 'utility.meter.replacement'
    _description = 'سجل استبدال العداد'
    _order = 'replacement_date desc'

    order_number = fields.Char('رقم العملية', default=lambda self: _('New'), readonly=True)
    replacement_date = fields.Date('تاريخ الاستبدال', default=fields.Date.today)
    old_meter_final_reading = fields.Float('القراءة النهائية للقديم')
    new_meter_initial_reading = fields.Float('القراءة الابتدائية للجديد', default=0.0)
    unbilled_consumption = fields.Float('الاستهلاك غير المفوتر للقديم', compute='_compute_unbilled_consumption', store=True)
    replacement_notes = fields.Text('ملاحظات الاستبدال')
    picking_ids = fields.One2many('stock.picking', compute='_compute_picking_ids', string='حركات المخزون')
    picking_count = fields.Integer(compute='_compute_picking_ids', string='عدد حركات المخزون')

    def _compute_picking_ids(self):
        for rec in self:
            pickings = self.env['stock.picking'].search([('origin', '=', rec.order_number or rec.name)])
            rec.picking_ids = pickings
            rec.picking_count = len(pickings)

    @api.depends('old_meter_final_reading', 'utility_account_id.last_invoice_reading')
    def _compute_unbilled_consumption(self):
        for rec in self:
            last_invoiced = rec.utility_account_id.last_invoice_reading or 0.0
            rec.unbilled_consumption = max(0.0, rec.old_meter_final_reading - last_invoiced)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('order_number', _('New')) == _('New'):
                vals['order_number'] = self.env['ir.sequence'].next_by_code('utility.meter.replacement') or _('New')
        return super().create(vals_list)


    def _create_stock_picking(self, meter, location_dest_usage):
        if not meter.product_id:
            return False
            
        stock_location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        customer_location = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        scrap_location = self.env.ref('stock.stock_location_scrapped', raise_if_not_found=False)
        
        if not stock_location or not customer_location:
            return False
            
        loc_id = stock_location.id if location_dest_usage == 'customer' else customer_location.id
        dest_id = customer_location.id if location_dest_usage == 'customer' else (scrap_location.id if scrap_location else stock_location.id)
        
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing' if location_dest_usage == 'customer' else 'incoming'), ('company_id', '=', self.env.company.id)], limit=1)
        if not picking_type:
            return False
            
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': loc_id,
            'location_dest_id': dest_id,
            'origin': self.order_number,
        })
        
        move = self.env['stock.move'].create({
            'name': meter.meter_number,
            'product_id': meter.product_id.id,
            'product_uom_qty': 1,
            'product_uom': meter.product_id.uom_id.id,
            'picking_id': picking.id,
            'location_id': loc_id,
            'location_dest_id': dest_id,
        })
        
        if meter.lot_id:
            self.env['stock.move.line'].create({
                'move_id': move.id,
                'product_id': meter.product_id.id,
                'product_uom_id': meter.product_id.uom_id.id,
                'qty_done': 1,
                'lot_id': meter.lot_id.id,
                'picking_id': picking.id,
                'location_id': loc_id,
                'location_dest_id': dest_id,
            })
        
        picking.action_confirm()
        picking.button_validate()
        return picking

    def action_complete_replacement(self):
        """Complete logistics around the unified core replacement flow."""
        self.ensure_one()
        if self.state == 'done':
            raise ValidationError(_('هذه العملية مكتملة بالفعل!'))
        self.write({
            'old_closing_reading': self.old_meter_final_reading,
            'new_opening_reading': self.new_meter_initial_reading,
            'replace_date': fields.Datetime.to_datetime(self.replacement_date),
        })
        old_meter = self.old_meter_id
        new_meter = self.new_meter_id
        result = self._action_confirm_replacement_unified()
        self._create_stock_picking(old_meter, 'scrap')
        self._create_stock_picking(new_meter, 'customer')
        return result
