from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ConstructionVariation(models.Model):
    _name = 'construction.variation'
    _description = 'Variation Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='project_id.company_id', store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project', string='Project',
                                 required=True, tracking=True, index=True)
    name = fields.Char(string='Variation Reference', required=True, index=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.today,
                       tracking=True)
    description = fields.Text(string='Description', required=True)
    reason = fields.Text(string='Reason')

    variation_type = fields.Selection([
        ('client', 'Client Variation'),
        ('consultant', 'Consultant Variation'),
        ('internal', 'Internal Variation'),
        ('design', 'Design Change'),
        ('quantity', 'Quantity Change'),
        ('rate', 'Rate Revision'),
    ], string='Variation Type', required=True, default='client', tracking=True)

    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='normal', index=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('implemented', 'Implemented'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    submitted_by = fields.Many2one('res.users', string='Submitted By',
                                   tracking=True)
    approved_by = fields.Many2one('res.users', string='Approved By',
                                  tracking=True)

    line_ids = fields.One2many('construction.variation.line', 'variation_id',
                               string='Variation Lines', copy=True)
    line_count = fields.Integer(string='Line Count',
                                compute='_compute_line_count', store=True)

    original_amount = fields.Monetary(string='Original Amount',
                                      compute='_compute_amounts', store=True)
    revised_amount = fields.Monetary(string='Revised Amount',
                                     compute='_compute_amounts', store=True)
    net_change = fields.Monetary(string='Net Change',
                                 compute='_compute_amounts', store=True)
    impact_percent = fields.Float(string='Impact %',
                                  compute='_compute_amounts', store=True,
                                  digits=(5, 2))

    budget_impact = fields.Text(string='Budget Impact Notes')
    schedule_impact = fields.Text(string='Schedule Impact Notes')
    cost_impact = fields.Text(string='Cost Impact Notes')
    approved_date = fields.Date(string='Approval Date')
    implemented_date = fields.Date(string='Implemented Date')

    note = fields.Text(string='Internal Notes')

    _sql_constraints = [
        ('name_project_unique', 'UNIQUE(name, project_id)',
         'Variation reference must be unique per project!'),
    ]

    @api.depends('line_ids', 'line_ids.original_amount', 'line_ids.revised_amount')
    def _compute_amounts(self):
        for rec in self:
            original = sum(rec.line_ids.mapped('original_amount'))
            revised = sum(rec.line_ids.mapped('revised_amount'))
            rec.original_amount = original
            rec.revised_amount = revised
            rec.net_change = revised - original
            rec.impact_percent = ((revised - original) / original * 100) if original else 0.0

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def action_submit(self):
        if not self.line_ids:
            raise UserError(_('Cannot submit a variation with no lines!'))
        self.write({
            'state': 'submitted',
            'submitted_by': self.env.user.id,
        })

    def action_review(self):
        self.write({'state': 'review'})

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approved_date': fields.Date.today(),
        })

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_implement(self):
        self.write({
            'state': 'implemented',
            'implemented_date': fields.Date.today(),
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                seq = self.env['ir.sequence'].next_by_code('construction.variation')
                vals['name'] = seq or '/'
        return super().create(vals_list)


class ConstructionVariationLine(models.Model):
    _name = 'construction.variation.line'
    _description = 'Variation Order Line'
    _order = 'variation_id, sequence'

    active = fields.Boolean(default=True)
    variation_id = fields.Many2one('construction.variation', string='Variation',
                                   required=True, ondelete='cascade', index=True)
    project_id = fields.Many2one('construction.project',
                                 related='variation_id.project_id', store=True, index=True)
    company_id = fields.Many2one('res.company',
                                 related='variation_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    sequence = fields.Integer(default=10)
    boq_item_id = fields.Many2one('construction.boq.item', string='BOQ Item',
                                  required=True, index=True)
    name = fields.Char(string='Description', compute='_compute_name', store=True)

    change_type = fields.Selection([
        ('quantity', 'Quantity Change'),
        ('rate', 'Rate Revision'),
        ('new_item', 'New Item'),
        ('delete_item', 'Delete Item'),
        ('price_adjustment', 'Price Adjustment'),
    ], string='Change Type', required=True, default='quantity')

    original_quantity = fields.Float(string='Original Quantity', default=0.0,
                                     digits=(16, 3))
    revised_quantity = fields.Float(string='Revised Quantity', default=0.0,
                                    digits=(16, 3))
    original_rate = fields.Monetary(string='Original Rate', default=0.0)
    revised_rate = fields.Monetary(string='Revised Rate', default=0.0)
    original_amount = fields.Monetary(string='Original Amount',
                                      compute='_compute_amounts', store=True)
    revised_amount = fields.Monetary(string='Revised Amount',
                                     compute='_compute_amounts', store=True)
    net_change = fields.Monetary(string='Net Change',
                                 compute='_compute_amounts', store=True)
    description_change = fields.Text(string='Description of Change')
    justification = fields.Text(string='Justification')
    note = fields.Text(string='Notes')

    @api.depends('boq_item_id', 'boq_item_id.name')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.boq_item_id.name if rec.boq_item_id else ''

    @api.depends('original_quantity', 'revised_quantity', 'original_rate',
                 'revised_rate')
    def _compute_amounts(self):
        for rec in self:
            rec.original_amount = rec.original_quantity * rec.original_rate
            rec.revised_amount = rec.revised_quantity * rec.revised_rate
            rec.net_change = rec.revised_amount - rec.original_amount

    @api.onchange('boq_item_id')
    def _onchange_boq_item(self):
        if self.boq_item_id:
            self.name = self.boq_item_id.name
            self.original_quantity = self.boq_item_id.quantity
            self.original_rate = self.boq_item_id.rate
            self.revised_quantity = self.boq_item_id.quantity
            self.revised_rate = self.boq_item_id.rate
