from odoo import api, fields, models


class ConstructionForecast(models.Model):
    _name = 'construction.forecast'
    _description = 'Construction Forecast'
    _order = 'date, id'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='project_id.company_id', store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project', string='Project',
                                 required=True, index=True)
    boq_item_id = fields.Many2one('construction.boq.item', string='BOQ Item',
                                  index=True)
    name = fields.Char(string='Description', compute='_compute_name', store=True)
    date = fields.Date(string='Forecast Date', required=True, index=True)
    period = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ], string='Period Type', default='monthly')

    forecast_type = fields.Selection([
        ('cost', 'Cost Forecast'),
        ('revenue', 'Revenue Forecast'),
        ('resource', 'Resource Forecast'),
        ('cashflow', 'Cash Flow Forecast'),
    ], string='Forecast Type', required=True, default='cost', index=True)

    planned_amount = fields.Monetary(string='Planned Amount', default=0.0)
    forecast_amount = fields.Monetary(string='Forecast Amount', default=0.0)
    actual_amount = fields.Monetary(string='Actual Amount', default=0.0)
    variance = fields.Monetary(string='Variance',
                               compute='_compute_variance', store=True)
    confidence = fields.Selection([
        ('low', 'Low (60-70%)'),
        ('medium', 'Medium (70-85%)'),
        ('high', 'High (85-95%)'),
        ('certain', 'Certain (95-100%)'),
    ], string='Confidence Level', default='medium')

    planned_quantity = fields.Float(string='Planned Quantity', digits=(16, 3))
    forecast_quantity = fields.Float(string='Forecast Quantity', digits=(16, 3))
    unit_cost = fields.Monetary(string='Unit Cost', default=0.0)

    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('forecast_unique',
         'UNIQUE(project_id, boq_item_id, date, forecast_type)',
         'Duplicate forecast record!'),
    ]

    @api.depends('boq_item_id', 'boq_item_id.name')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.boq_item_id.name if rec.boq_item_id else 'Forecast'

    @api.depends('forecast_amount', 'planned_amount')
    def _compute_variance(self):
        for rec in self:
            rec.variance = rec.forecast_amount - rec.planned_amount

    @api.model
    def cron_update_from_actuals(self):
        cost_entries = self.env['construction.cost.entry'].search([
            ('date', '>=', fields.Date.today().replace(day=1)),
        ])
        for entry in cost_entries:
            forecast = self.search([
                ('project_id', '=', entry.project_id.id),
                ('boq_item_id', '=', entry.boq_item_id.id),
                ('forecast_type', '=', 'cost'),
                ('date', '=', entry.date),
            ], limit=1)
            if forecast:
                forecasts = self.search([
                    ('project_id', '=', entry.project_id.id),
                    ('boq_item_id', '=', entry.boq_item_id.id),
                    ('forecast_type', '=', 'cost'),
                ])
                total_actual = sum(forecasts.mapped('actual_amount')) + entry.amount
                forecasts.write({'actual_amount': total_actual})
