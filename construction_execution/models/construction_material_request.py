from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ConstructionMaterialRequest(models.Model):
    _name = 'construction.material.request'
    _description = 'Material Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project', string='Project',
                                 required=True, tracking=True, index=True)
    name = fields.Char(string='Request Reference', required=True, index=True,
                       default=lambda self: _('New'))
    date = fields.Date(string='Request Date', required=True,
                       default=fields.Date.today, tracking=True)
    required_date = fields.Date(string='Required Date', tracking=True)
    requested_by = fields.Many2one('res.users', string='Requested By',
                                   default=lambda self: self.env.user,
                                   tracking=True)
    approved_by = fields.Many2one('res.users', string='Approved By',
                                  tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('ordered', 'Ordered'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    line_ids = fields.One2many('construction.material.request.line', 'request_id',
                               string='Request Lines', copy=True)
    line_count = fields.Integer(string='Line Count',
                                compute='_compute_line_count', store=True)
    total_quantity = fields.Float(string='Total Quantity',
                                  compute='_compute_totals', store=True,
                                  digits=(16, 3))
    total_cost = fields.Monetary(string='Total Cost',
                                 compute='_compute_totals', store=True)

    purchase_order_ids = fields.One2many('purchase.order', string='Purchase Orders',
                                         compute='_compute_purchase_orders')
    has_purchase_orders = fields.Boolean(string='Has Purchase Orders',
                                         compute='_compute_purchase_orders')
    picking_ids = fields.One2many('stock.picking', string='Receipts',
                                  compute='_compute_pickings')
    has_receipts = fields.Boolean(string='Has Receipts',
                                  compute='_compute_pickings')

    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_company_unique', 'UNIQUE(name, company_id)',
         'Request name must be unique per company!'),
    ]

    @api.depends('line_ids', 'line_ids.quantity', 'line_ids.total_cost')
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids
            rec.total_quantity = sum(lines.mapped('quantity'))
            rec.total_cost = sum(lines.mapped('total_cost'))

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def _compute_purchase_orders(self):
        for rec in self:
            orders = self.env['purchase.order'].search([
                ('construction_material_request_id', '=', rec.id)])
            if not orders:
                orders = self.env['purchase.order'].search([
                    ('origin', 'ilike', rec.name)])
            rec.purchase_order_ids = orders
            rec.has_purchase_orders = bool(orders)

    def _compute_pickings(self):
        for rec in self:
            pickings = self.env['stock.picking'].search([
                ('origin', 'ilike', rec.name)])
            rec.picking_ids = pickings
            rec.has_receipts = bool(pickings)

    def action_submit(self):
        if not self.line_ids:
            raise UserError(_('Cannot submit a request with no lines!'))
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
        })

    def action_ordered(self):
        self.write({'state': 'ordered'})

    def action_receive(self):
        self.write({'state': 'received'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_create_purchase_order(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.product_id and l.quantity > 0)
        if not lines:
            raise UserError(_('No purchasable items in this request!'))
        po_vals = {
            'partner_id': self.project_id.partner_id.id or self.env.user.partner_id.id,
            'origin': self.name,
            'date_order': fields.Datetime.now(),
            'state': 'draft',
            'construction_project_id': self.project_id.id,
            'construction_material_request_id': self.id,
            'order_line': [],
        }
        for line in lines:
            po_vals['order_line'].append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.name or line.product_id.display_name,
                'product_qty': line.quantity,
                'product_uom': line.uom_id.id,
                'price_unit': line.unit_cost or line.product_id.standard_price,
                'date_planned': fields.Datetime.now(),
                'construction_material_request_line_id': line.id,
                'construction_boq_item_id': line.boq_item_id.id,
            }))
        po = self.env['purchase.order'].create(po_vals)
        self.write({'state': 'ordered'})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': po.id,
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                seq = self.env['ir.sequence'].next_by_code('construction.material.request')
                vals['name'] = seq or '/'
        return super().create(vals_list)


class ConstructionMaterialRequestLine(models.Model):
    _name = 'construction.material.request.line'
    _description = 'Material Request Line'
    _order = 'request_id, sequence'

    active = fields.Boolean(default=True)
    request_id = fields.Many2one('construction.material.request', string='Request',
                                 required=True, ondelete='cascade', index=True)
    project_id = fields.Many2one('construction.project',
                                 related='request_id.project_id', store=True, index=True)
    company_id = fields.Many2one('res.company', related='request_id.company_id',
                                 store=True)
    sequence = fields.Integer(default=10)
    material_plan_id = fields.Many2one('construction.material.plan',
                                       string='Material Plan', index=True)
    boq_item_id = fields.Many2one('construction.boq.item', string='BOQ Item',
                                  index=True)
    product_id = fields.Many2one('product.product', string='Product',
                                 required=True, index=True)
    resource_id = fields.Many2one('construction.resource', string='Resource')
    name = fields.Char(string='Description', compute='_compute_name', store=True)
    uom_id = fields.Many2one('uom.uom', string='Unit',
                             related='product_id.uom_id', store=True)
    quantity = fields.Float(string='Quantity', required=True, default=0.0,
                            digits=(16, 3))
    received_quantity = fields.Float(string='Received Quantity', default=0.0,
                                     digits=(16, 3))
    remaining_quantity = fields.Float(string='Remaining Quantity',
                                      compute='_compute_remaining', store=True,
                                      digits=(16, 3))
    unit_cost = fields.Monetary(string='Unit Cost', default=0.0)
    total_cost = fields.Monetary(string='Total Cost',
                                 compute='_compute_total_cost', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    note = fields.Text(string='Notes')

    @api.depends('product_id', 'product_id.display_name')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.product_id.display_name if rec.product_id else ''

    @api.depends('quantity', 'received_quantity')
    def _compute_remaining(self):
        for rec in self:
            rec.remaining_quantity = rec.quantity - rec.received_quantity

    @api.depends('quantity', 'unit_cost')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.quantity * rec.unit_cost

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id.id
            self.unit_cost = self.product_id.standard_price


class ConstructionMaterialRequestStatus(models.Model):
    _name = 'construction.material.request.status'
    _description = 'Material Request Status'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)
