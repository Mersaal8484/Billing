from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ConstructionMaterialReturn(models.Model):
    _name = 'construction.material.return'
    _description = 'Material Return to Store'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project', string='Project',
                                 required=True, tracking=True, index=True)
    name = fields.Char(string='Reference', required=True, index=True,
                       default=lambda self: _('New'))
    date = fields.Date(string='Return Date', required=True,
                       default=fields.Date.today, tracking=True)
    returned_by = fields.Many2one('res.users', string='Returned By',
                                  default=lambda self: self.env.user, tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    line_ids = fields.One2many('construction.material.return.line', 'return_id',
                               string='Return Lines', copy=True)
    line_count = fields.Integer(string='Line Count',
                                compute='_compute_line_count', store=True)
    total_quantity = fields.Float(string='Total Quantity',
                                  compute='_compute_totals', store=True,
                                  digits=(16, 3))
    picking_id = fields.Many2one('stock.picking', string='Stock Picking')
    source_location_id = fields.Many2one('stock.location',
        string='Source Site Location',
        domain="[('usage', '=', 'production')]")
    destination_location_id = fields.Many2one('stock.location',
        string='Destination Store Location',
        domain="[('usage', '=', 'internal')]",
        default=lambda self: self.env.ref(
            'stock.stock_location_stock', raise_if_not_found=False))

    reason = fields.Text(string='Return Reason')
    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_company_unique', 'UNIQUE(name, company_id)',
         'Return reference must be unique per company!'),
    ]

    @api.depends('line_ids', 'line_ids.quantity')
    def _compute_totals(self):
        for rec in self:
            rec.total_quantity = sum(rec.line_ids.mapped('quantity'))

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def action_confirm(self):
        self.state = 'confirmed'

    def action_done(self):
        self.state = 'done'

    def action_cancel(self):
        self.state = 'cancelled'

    def action_draft(self):
        self.state = 'draft'

    def action_create_stock_return_picking(self):
        self.ensure_one()
        if not self.source_location_id:
            raise UserError(_('Please set a source site location first!'))
        lines = self.line_ids.filtered(lambda l: l.product_id and l.quantity > 0)
        if not lines:
            raise UserError(_('No valid lines to return!'))
        dest = self.destination_location_id or self.env.ref('stock.stock_location_stock')
        move_lines = []
        for line in lines:
            move_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': dest.id,
                'name': line.name or line.product_id.display_name,
                'construction_material_return_line_id': line.id,
            }))
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.env.ref('stock.picking_type_internal').id,
            'location_id': self.source_location_id.id,
            'location_dest_id': dest.id,
            'partner_id': self.project_id.partner_id.id,
            'origin': self.name,
            'construction_project_id': self.project_id.id,
            'construction_material_return_id': self.id,
            'move_ids_without_package': move_lines,
        })
        self.picking_id = picking.id
        self.state = 'confirmed'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock Picking'),
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                seq = self.env['ir.sequence'].next_by_code('construction.material.return')
                vals['name'] = seq or '/'
        return super().create(vals_list)


class ConstructionMaterialReturnLine(models.Model):
    _name = 'construction.material.return.line'
    _description = 'Material Return Line'
    _order = 'return_id, sequence'

    return_id = fields.Many2one('construction.material.return', string='Return',
                                required=True, ondelete='cascade', index=True)
    project_id = fields.Many2one('construction.project',
                                 related='return_id.project_id', store=True)
    company_id = fields.Many2one('res.company', related='return_id.company_id',
                                 store=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', string='Product',
                                 required=True, index=True)
    boq_item_id = fields.Many2one('construction.boq.item', string='BOQ Item',
                                  index=True)
    name = fields.Char(string='Description', compute='_compute_name', store=True)
    uom_id = fields.Many2one('uom.uom', string='Unit',
                             related='product_id.uom_id', store=True)
    quantity = fields.Float(string='Quantity', required=True, default=0.0,
                            digits=(16, 3))
    condition = fields.Selection([
        ('new', 'New/Unused'),
        ('good', 'Good Condition'),
        ('damaged', 'Damaged'),
        ('waste', 'Waste/Scrap'),
    ], string='Condition', default='good', required=True)
    reason = fields.Text(string='Return Reason')
    note = fields.Text(string='Notes')

    @api.depends('product_id', 'product_id.display_name')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.product_id.display_name if rec.product_id else ''
