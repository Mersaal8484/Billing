from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ConstructionProgress(models.Model):
    _name = 'construction.progress'
    _description = 'Progress Measurement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='project_id.company_id', store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project', string='Project',
                                 required=True, tracking=True, index=True)
    name = fields.Char(string='Reference', required=True, index=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.today,
                       tracking=True)
    period = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    ], string='Period', required=True, default='weekly', tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    submitted_by = fields.Many2one('res.users', string='Submitted By', tracking=True)
    approved_by = fields.Many2one('res.users', string='Approved By', tracking=True)
    approved_date = fields.Date(string='Approval Date')

    line_ids = fields.One2many('construction.progress.line', 'progress_id',
                               string='Progress Lines', copy=True)
    line_count = fields.Integer(string='Line Count',
                                compute='_compute_line_count', store=True)

    executed_percent = fields.Float(string='Overall Progress %',
                                    compute='_compute_overall', store=True,
                                    digits=(5, 2), group_operator='avg')
    total_executed = fields.Monetary(string='Total Executed Value',
                                     compute='_compute_overall', store=True)
    total_remaining = fields.Monetary(string='Total Remaining Value',
                                      compute='_compute_overall', store=True)

    note = fields.Text(string='Notes')
    weather_conditions = fields.Char(string='Weather Conditions')
    manpower_on_site = fields.Integer(string='Manpower on Site')
    equipment_on_site = fields.Integer(string='Equipment on Site')
    work_description = fields.Text(string='Work Description')
    challenges = fields.Text(string='Challenges/Issues')
    plan_next_period = fields.Text(string='Plan for Next Period')

    _sql_constraints = [
        ('check_percent_range', 'CHECK(executed_percent >= 0 AND executed_percent <= 100)',
         'Progress percentage must be between 0 and 100!'),
    ]

    @api.depends('line_ids', 'line_ids.executed_percent', 'line_ids.executed_amount')
    def _compute_overall(self):
        for rec in self:
            lines = rec.line_ids
            total = sum(lines.mapped('total_amount')) or 1.0
            executed = sum(lines.mapped('executed_amount'))
            rec.total_executed = executed
            rec.total_remaining = sum(lines.mapped('remaining_amount'))
            rec.executed_percent = (executed / total * 100) if total else 0.0

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def action_submit(self):
        if not self.line_ids:
            raise UserError(_('Cannot submit progress with no lines!'))
        self.write({
            'state': 'submitted',
            'submitted_by': self.env.user.id,
        })

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approved_date': fields.Date.today(),
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_generate_lines(self):
        self.ensure_one()
        items = self.env['construction.boq.item'].search([
            ('project_id', '=', self.project_id.id),
            ('boq_id.state', '=', 'approved'),
        ])
        existing = self.line_ids.mapped('boq_item_id.id')
        for item in items:
            if item.id not in existing:
                self.env['construction.progress.line'].create({
                    'progress_id': self.id,
                    'boq_item_id': item.id,
                    'previous_quantity': item.executed_quantity,
                    'current_quantity': 0.0,
                    'total_quantity': item.quantity,
                    'unit_rate': item.rate,
                })

    @api.model
    def cron_create_monthly_snapshot(self):
        projects = self.env['construction.project'].search([
            ('active', '=', True),
            ('project_stage', 'in', ('execution', 'planning')),
        ])
        for project in projects:
            existing = self.search([
                ('project_id', '=', project.id),
                ('period', '=', 'monthly'),
                ('date', '>=', fields.Date.today().replace(day=1)),
            ], limit=1)
            if not existing:
                progress = self.create({
                    'project_id': project.id,
                    'date': fields.Date.today(),
                    'period': 'monthly',
                })
                progress.action_generate_lines()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                seq = self.env['ir.sequence'].next_by_code('construction.progress')
                vals['name'] = seq or '/'
        return super().create(vals_list)


class ConstructionProgressLine(models.Model):
    _name = 'construction.progress.line'
    _description = 'Progress Line'
    _order = 'progress_id, sequence'

    active = fields.Boolean(default=True)
    progress_id = fields.Many2one('construction.progress', string='Progress',
                                  required=True, ondelete='cascade', index=True)
    project_id = fields.Many2one('construction.project',
                                 related='progress_id.project_id', store=True, index=True)
    company_id = fields.Many2one('res.company',
                                 related='progress_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    sequence = fields.Integer(default=10)
    boq_item_id = fields.Many2one('construction.boq.item', string='BOQ Item',
                                  required=True, index=True)
    name = fields.Char(string='Description', compute='_compute_name', store=True)

    total_quantity = fields.Float(string='Total Quantity', digits=(16, 3))
    previous_quantity = fields.Float(string='Previous Quantity', digits=(16, 3))
    current_quantity = fields.Float(string='Current Quantity', digits=(16, 3))
    total_executed = fields.Float(string='Total Executed Qty',
                                  compute='_compute_totals', store=True,
                                  digits=(16, 3))
    remaining_quantity = fields.Float(string='Remaining Qty',
                                      compute='_compute_totals', store=True,
                                      digits=(16, 3))
    executed_percent = fields.Float(string='Executed %',
                                    compute='_compute_totals', store=True,
                                    digits=(5, 2))

    unit_rate = fields.Monetary(string='Unit Rate', default=0.0)
    previous_amount = fields.Monetary(string='Previous Amount',
                                      compute='_compute_amounts', store=True)
    current_amount = fields.Monetary(string='Current Amount',
                                     compute='_compute_amounts', store=True)
    total_amount = fields.Monetary(string='Total Amount',
                                   compute='_compute_amounts', store=True)
    executed_amount = fields.Monetary(string='Executed Amount',
                                      compute='_compute_amounts', store=True)
    remaining_amount = fields.Monetary(string='Remaining Amount',
                                       compute='_compute_amounts', store=True)

    note = fields.Text(string='Notes')

    @api.depends('boq_item_id', 'boq_item_id.name')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.boq_item_id.display_name if rec.boq_item_id else ''

    @api.depends('previous_quantity', 'current_quantity', 'total_quantity')
    def _compute_totals(self):
        for rec in self:
            rec.total_executed = rec.previous_quantity + rec.current_quantity
            rec.remaining_quantity = rec.total_quantity - rec.total_executed
            rec.executed_percent = (rec.total_executed / rec.total_quantity * 100) if rec.total_quantity else 0.0

    @api.depends('total_quantity', 'unit_rate', 'total_executed')
    def _compute_amounts(self):
        for rec in self:
            rec.previous_amount = rec.previous_quantity * rec.unit_rate
            rec.current_amount = rec.current_quantity * rec.unit_rate
            rec.total_amount = rec.total_quantity * rec.unit_rate
            rec.executed_amount = rec.total_executed * rec.unit_rate
            rec.remaining_amount = rec.remaining_quantity * rec.unit_rate

    @api.onchange('boq_item_id')
    def _onchange_boq_item(self):
        if self.boq_item_id:
            self.name = self.boq_item_id.display_name
            self.total_quantity = self.boq_item_id.quantity
            self.unit_rate = self.boq_item_id.rate
            self.previous_quantity = self.boq_item_id.executed_quantity
