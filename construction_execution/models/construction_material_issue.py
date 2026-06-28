from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ConstructionMaterialIssue(models.Model):
    _name = 'construction.material.issue'
    _description = 'Material Issue to Site'
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
    date = fields.Date(string='Issue Date', required=True,
                       default=fields.Date.today, tracking=True)
    issued_by = fields.Many2one('res.users', string='Issued By',
                                default=lambda self: self.env.user,
                                tracking=True)
    received_by = fields.Many2one('res.partner', string='Received By')
    location_id = fields.Many2one('stock.location', string='Site Location',
                                  domain="[('usage', '=', 'production')]")
    source_location_id = fields.Many2one('stock.location', string='Source Location',
                                         domain="[('usage', '=', 'internal')]",
                                         default=lambda self: self.env.ref(
                                             'stock.stock_location_stock', raise_if_not_found=False))
    picking_id = fields.Many2one('stock.picking', string='Stock Picking')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    line_ids = fields.One2many('construction.material.issue.line', 'issue_id',
                               string='Issue Lines', copy=True)
    line_count = fields.Integer(string='Line Count',
                                compute='_compute_line_count', store=True)
    total_quantity = fields.Float(string='Total Quantity',
                                  compute='_compute_totals', store=True,
                                  digits=(16, 3))
    total_cost = fields.Monetary(string='Total Cost',
                                 compute='_compute_totals', store=True)
    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_company_unique', 'UNIQUE(name, company_id)',
         'Issue reference must be unique per company!'),
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

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def _create_cost_entries_from_issue(self):
        CostEntry = self.env['construction.cost.entry']
        for line in self.line_ids.filtered(lambda l: l.product_id and l.total_cost):
            CostEntry.create({
                'project_id': self.project_id.id,
                'boq_item_id': line.boq_item_id.id,
                'name': f'{self.name}: {line.name or line.product_id.display_name}',
                'date': self.date,
                'ref': self.name,
                'cost_type': 'material',
                'amount': line.total_cost,
                'quantity': line.quantity,
                'account_id': line.product_id.property_account_expense_id.id or
                              line.product_id.categ_id.property_account_expense_categ_id.id,
                'analytic_account_id': self.project_id.analytic_account_id.id,
            })

    def action_create_stock_picking(self):
        self.ensure_one()
        if not self.location_id:
            raise UserError(_('Please set a site location first!'))
        lines = self.line_ids.filtered(lambda l: l.product_id and l.quantity > 0)
        if not lines:
            raise UserError(_('No valid lines to issue!'))
        move_lines = []
        for line in lines:
            move_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.uom_id.id or line.product_id.uom_id.id,
                'location_id': self.source_location_id.id or self.env.ref('stock.stock_location_stock').id,
                'location_dest_id': self.location_id.id,
                'name': line.name or line.product_id.display_name,
                'construction_material_issue_line_id': line.id,
                'construction_boq_item_id': line.boq_item_id.id,
            }))
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.env.ref('stock.picking_type_internal').id,
            'location_id': self.source_location_id.id or self.env.ref('stock.stock_location_stock').id,
            'location_dest_id': self.location_id.id,
            'partner_id': self.project_id.partner_id.id,
            'origin': self.name,
            'construction_project_id': self.project_id.id,
            'construction_material_issue_id': self.id,
            'move_ids_without_package': move_lines,
        })
        self.picking_id = picking.id
        self.state = 'confirmed'
        self._create_cost_entries_from_issue()
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
                seq = self.env['ir.sequence'].next_by_code('construction.material.issue')
                vals['name'] = seq or '/'
        return super().create(vals_list)


class ConstructionMaterialIssueLine(models.Model):
    _name = 'construction.material.issue.line'
    _description = 'Material Issue Line'
    _order = 'issue_id, sequence'

    issue_id = fields.Many2one('construction.material.issue', string='Issue',
                               required=True, ondelete='cascade', index=True)
    project_id = fields.Many2one('construction.project',
                                 related='issue_id.project_id', store=True, index=True)
    company_id = fields.Many2one('res.company', related='issue_id.company_id',
                                 store=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', string='Product',
                                 required=True, index=True)
    resource_id = fields.Many2one('construction.resource', string='Resource')
    boq_item_id = fields.Many2one('construction.boq.item', string='BOQ Item',
                                  index=True)
    name = fields.Char(string='Description', compute='_compute_name', store=True)
    uom_id = fields.Many2one('uom.uom', string='Unit',
                             related='product_id.uom_id', store=True)
    quantity = fields.Float(string='Quantity', required=True, default=0.0,
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

    @api.depends('quantity', 'unit_cost')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.quantity * rec.unit_cost
