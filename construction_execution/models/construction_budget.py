from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ConstructionBudget(models.Model):
    _name = 'construction.budget'
    _description = 'Construction Budget'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='project_id.company_id', store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project', string='Project',
                                 required=True, tracking=True, index=True)
    name = fields.Char(string='Budget Name', required=True)
    version = fields.Char(string='Version', default='1.0', tracking=True)
    date = fields.Date(string='Date', default=fields.Date.today, tracking=True)
    description = fields.Text(string='Description')

    budget_type = fields.Selection([
       ('original', 'Original Budget'),
        ('revised', 'Revised Budget'),
        ('supplementary', 'Supplementary Budget'),
        ('final', 'Final Account'),
    ], string='Budget Type', required=True, default='original', index=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('frozen', 'Frozen'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    line_ids = fields.One2many('construction.budget.line', 'budget_id',
                               string='Budget Lines', copy=True)
    line_count = fields.Integer(string='Line Count',
                                compute='_compute_line_count', store=True)
    total_amount = fields.Monetary(string='Total Amount',
                                   compute='_compute_totals', store=True)
    contingency_percent = fields.Float(string='Contingency %', default=5.0,
                                       digits=(5, 2))
    contingency_amount = fields.Monetary(string='Contingency Amount',
                                         compute='_compute_totals', store=True)
    grand_total = fields.Monetary(string='Grand Total',
                                  compute='_compute_totals', store=True)

    approved_by = fields.Many2one('res.users', string='Approved By', tracking=True)
    approved_date = fields.Date(string='Approval Date')
    freeze_date = fields.Date(string='Freeze Date')

    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('check_contingency', 'CHECK(contingency_percent >= 0 AND contingency_percent <= 100)',
         'Contingency must be between 0 and 100!'),
    ]

    @api.depends('line_ids', 'line_ids.amount', 'contingency_percent')
    def _compute_totals(self):
        for rec in self:
            total = sum(rec.line_ids.mapped('amount'))
            rec.total_amount = total
            rec.contingency_amount = total * rec.contingency_percent / 100
            rec.grand_total = total + rec.contingency_amount

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approved_date': fields.Date.today(),
        })

    def action_freeze(self):
        self.write({
            'state': 'frozen',
            'freeze_date': fields.Date.today(),
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_create_crossovered_budget(self):
        self.ensure_one()
        analytic = self.project_id.analytic_account_id
        if not analytic:
            raise UserError(_('The project must have an Analytic Account linked!'))

        crossovered = self.env['crossovered.budget'].create({
            'name': '%s - %s' % (self.project_id.code, self.name),
            'date_from': self.date or fields.Date.today(),
            'date_to': fields.Date.today(),
            'user_id': self.env.user.id,
            'company_id': self.company_id.id,
        })

        for line in self.line_ids:
            bpost = self._get_or_create_budget_post(line)
            crossovered.write({
                'crossovered_budget_line': [(0, 0, {
                    'general_budget_id': bpost.id,
                    'analytic_account_id': analytic.id,
                    'planned_amount': line.amount,
                    'date_from': self.date or fields.Date.today(),
                    'date_to': fields.Date.today(),
                })]
            })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Accounting Budget'),
            'res_model': 'crossovered.budget',
            'view_mode': 'form,tree',
            'res_id': crossovered.id,
            'context': {
                'default_name': crossovered.name,
                'default_date_from': crossovered.date_from,
                'default_date_to': crossovered.date_to,
            },
        }

    def _get_or_create_budget_post(self, line):
        if line.budget_post_id:
            return line.budget_post_id
        name = line.cost_code or line.name[:64]
        bpost = self.env['account.budget.post'].search([
            '|', ('name', '=', name), ('name', '=', line.cost_code),
        ], limit=1)
        if not bpost:
            account = self.env['account.account'].search([
                ('account_type', 'in', ['expense', 'expense_direct_cost']),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            bpost = self.env['account.budget.post'].create({
                'name': name,
                'account_ids': [(4, account.id)] if account else [],
                'company_id': self.company_id.id,
            })
        line.budget_post_id = bpost.id
        return bpost


class ConstructionBudgetLine(models.Model):
    _name = 'construction.budget.line'
    _description = 'Budget Line'
    _order = 'budget_id, sequence'

    active = fields.Boolean(default=True)
    budget_id = fields.Many2one('construction.budget', string='Budget',
                                required=True, ondelete='cascade', index=True)
    project_id = fields.Many2one('construction.project',
                                 related='budget_id.project_id', store=True, index=True)
    company_id = fields.Many2one('res.company', related='budget_id.company_id',
                                 store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    sequence = fields.Integer(default=10)
    boq_item_id = fields.Many2one('construction.boq.item', string='BOQ Item',
                                  index=True)
    resource_id = fields.Many2one('construction.resource', string='Resource',
                                  index=True)
    cost_code = fields.Char(string='Cost Code')
    name = fields.Char(string='Description', required=True)
    quantity = fields.Float(string='Quantity', default=0.0, digits=(16, 3))
    unit_cost = fields.Monetary(string='Unit Cost', default=0.0)
    amount = fields.Monetary(string='Amount', compute='_compute_amount', store=True)
    budget_post_id = fields.Many2one('account.budget.post', string='Budget Post',
                                     index=True, ondelete='restrict')
    note = fields.Text(string='Notes')

    @api.depends('quantity', 'unit_cost')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.quantity * rec.unit_cost
