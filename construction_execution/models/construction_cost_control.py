from odoo import api, fields, models


class ConstructionCostControl(models.Model):
    _name = 'construction.cost.control'
    _description = 'Cost Control'
    _order = 'project_id, boq_item_id'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='project_id.company_id', store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project', string='Project',
                                 required=True, index=True)
    boq_item_id = fields.Many2one('construction.boq.item', string='BOQ Item',
                                  index=True)
    resource_id = fields.Many2one('construction.resource', string='Resource',
                                  index=True)
    cost_code = fields.Char(string='Cost Code')

    budget_cost = fields.Monetary(string='Budget Cost', default=0.0)
    committed_cost = fields.Monetary(string='Committed Cost', default=0.0)
    actual_cost = fields.Monetary(string='Actual Cost', default=0.0)
    forecast_cost = fields.Monetary(string='Forecast Cost', default=0.0)
    remaining_cost = fields.Monetary(string='Remaining Cost',
                                     compute='_compute_variance', store=True)
    variance = fields.Monetary(string='Variance',
                               compute='_compute_variance', store=True)
    variance_percent = fields.Float(string='Variance %',
                                    compute='_compute_variance', store=True,
                                    digits=(5, 2))

    earned_value = fields.Monetary(string='Earned Value (EV)', default=0.0)
    planned_value = fields.Monetary(string='Planned Value (PV)', default=0.0)
    actual_cost_ev = fields.Monetary(string='Actual Cost (AC)', default=0.0)
    schedule_variance = fields.Monetary(string='Schedule Variance (SV)',
                                        compute='_compute_evm', store=True)
    cost_variance = fields.Monetary(string='Cost Variance (CV)',
                                    compute='_compute_evm', store=True)
    spi = fields.Float(string='SPI', compute='_compute_evm', store=True,
                       digits=(12, 4))
    cpi = fields.Float(string='CPI', compute='_compute_evm', store=True,
                       digits=(12, 4))
    eac = fields.Monetary(string='EAC', compute='_compute_evm', store=True)
    etc = fields.Monetary(string='ETC', compute='_compute_evm', store=True)
    bac = fields.Monetary(string='BAC', compute='_compute_evm', store=True)
    vac = fields.Monetary(string='VAC', compute='_compute_evm', store=True)

    date = fields.Date(string='Last Updated', default=fields.Date.today)
    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('cost_control_unique',
         'UNIQUE(project_id, boq_item_id, resource_id, cost_code)',
         'Cost control record must be unique!'),
    ]

    @api.model
    def cron_update_costs(self):
        projects = self.env['construction.project'].search([('active', '=', True)])
        for project in projects:
            for boq_item in project.boq_ids.item_ids:
                cost_entries = self.env['construction.cost.entry'].search([
                    ('project_id', '=', project.id),
                    ('boq_item_id', '=', boq_item.id),
                ])
                actual_cost = sum(cost_entries.mapped('amount'))
                record = self.search([
                    ('project_id', '=', project.id),
                    ('boq_item_id', '=', boq_item.id),
                ], limit=1)
                if not record:
                    record = self.create({
                        'project_id': project.id,
                        'boq_item_id': boq_item.id,
                        'budget_cost': boq_item.amount,
                    })
                record.write({
                    'actual_cost': actual_cost,
                    'date': fields.Date.today(),
                })

    @api.depends('budget_cost', 'committed_cost', 'actual_cost', 'forecast_cost')
    def _compute_variance(self):
        for rec in self:
            rec.remaining_cost = rec.budget_cost - rec.actual_cost
            rec.variance = rec.budget_cost - rec.actual_cost
            rec.variance_percent = (rec.variance / rec.budget_cost * 100) if rec.budget_cost else 0.0

    @api.depends('earned_value', 'planned_value', 'actual_cost_ev', 'budget_cost')
    def _compute_evm(self):
        for rec in self:
            ev = rec.earned_value or 0.0
            pv = rec.planned_value or 1.0
            ac = rec.actual_cost_ev or 1.0
            rec.schedule_variance = ev - pv
            rec.cost_variance = ev - ac
            rec.spi = ev / pv if pv else 0.0
            rec.cpi = ev / ac if ac else 0.0
            rec.bac = rec.budget_cost or ev
            rec.eac = rec.bac / rec.cpi if rec.cpi else 0.0
            rec.etc = rec.eac - ac
            rec.vac = rec.bac - rec.eac


class ConstructionCostEntry(models.Model):
    _name = 'construction.cost.entry'
    _description = 'Cost Entry'
    _order = 'date desc, id desc'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project', string='Project',
                                 required=True, index=True)
    boq_item_id = fields.Many2one('construction.boq.item', string='BOQ Item',
                                  index=True)
    resource_id = fields.Many2one('construction.resource', string='Resource',
                                  index=True)
    name = fields.Char(string='Description', required=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.today,
                       index=True)
    ref = fields.Char(string='Reference', index=True)

    cost_type = fields.Selection([
        ('material', 'Material'),
        ('labor', 'Labor'),
        ('equipment', 'Equipment'),
        ('subcontract', 'Subcontract'),
        ('overhead', 'Overhead'),
        ('other', 'Other'),
    ], string='Cost Type', required=True, default='material', index=True)

    amount = fields.Monetary(string='Amount', required=True)
    quantity = fields.Float(string='Quantity', default=1.0, digits=(16, 3))
    unit_price = fields.Monetary(string='Unit Price',
                                 compute='_compute_unit_price', store=True)
    is_billable = fields.Boolean(string='Billable to Client', default=False)

    account_id = fields.Many2one('account.account', string='Account',
                                 domain="[('company_id', '=', company_id)]")
    analytic_account_id = fields.Many2one('account.analytic.account',
                                          string='Analytic Account')
    purchase_line_id = fields.Many2one('purchase.order.line',
                                       string='Purchase Order Line')
    invoice_line_id = fields.Many2one('account.move.line',
                                      string='Invoice Line')
    account_move_id = fields.Many2one('account.move', string='Journal Entry')

    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('check_amount_positive', 'CHECK(amount >= 0)',
         'Cost amount must be positive!'),
    ]

    @api.depends('amount', 'quantity')
    def _compute_unit_price(self):
        for rec in self:
            rec.unit_price = rec.amount / rec.quantity if rec.quantity else 0.0
