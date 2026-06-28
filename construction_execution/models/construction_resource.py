from odoo import api, fields, models


class ConstructionResource(models.Model):
    _name = 'construction.resource'
    _description = 'Construction Resource'
    _order = 'code'
    _check_company_auto = True
    _rec_name = 'display_name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    code = fields.Char(string='Resource Code', required=True, index=True)
    name = fields.Char(string='Resource Name', required=True, translate=True)
    display_name = fields.Char(string='Display Name',
                               compute='_compute_display_name', store=True)
    arabic_name = fields.Char(string='Arabic Name')
    description = fields.Text(string='Description', translate=True)

    resource_type = fields.Selection([
        ('material', 'Material'),
        ('labor', 'Labor'),
        ('equipment', 'Equipment'),
        ('subcontract', 'Subcontract'),
        ('service', 'Service'),
    ], string='Resource Type', required=True, default='material', index=True)

    product_id = fields.Many2one('product.product', string='Product',
                                 domain=[('type', '!=', 'service')])
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    unit_cost = fields.Monetary(string='Unit Cost', default=0.0)
    overhead_percent = fields.Float(string='Overhead %', default=0.0,
                                    digits=(5, 2))
    profit_percent = fields.Float(string='Profit %', default=0.0, digits=(5, 2))
    total_cost = fields.Monetary(string='Total Cost',
                                 compute='_compute_total_cost', store=True)

    productivity_rate = fields.Float(string='Productivity Rate',
                                     digits=(16, 3),
                                     help='Units per hour/day')
    productivity_uom = fields.Selection([
        ('hour', 'Per Hour'),
        ('day', 'Per Day'),
        ('week', 'Per Week'),
    ], string='Productivity Period', default='day')

    supplier_ids = fields.Many2many('res.partner', string='Suppliers')
    lead_time = fields.Integer(string='Lead Time (Days)', default=0)
    stock_available = fields.Float(string='Available Stock', digits=(16, 3))
    stock_reserved = fields.Float(string='Reserved Stock', digits=(16, 3))
    stock_forecast = fields.Float(string='Forecast Stock', digits=(16, 3))
    is_rental = fields.Boolean(string='Rental Equipment')
    rental_cost = fields.Monetary(string='Rental Cost/Day')
    operator_required = fields.Boolean(string='Operator Required')
    operator_cost = fields.Monetary(string='Operator Cost/Day')

    rate_analysis_count = fields.Integer(string='Rate Analyses',
                                         compute='_compute_rate_analysis_count')
    material_plan_count = fields.Integer(string='Material Plans',
                                         compute='_compute_material_plan_count')

    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('resource_code_company_unique', 'UNIQUE(code, company_id)',
         'Resource code must be unique per company!'),
    ]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'[{rec.code}] {rec.name}'

    @api.depends('unit_cost', 'overhead_percent', 'profit_percent')
    def _compute_total_cost(self):
        for rec in self:
            cost = rec.unit_cost
            cost += cost * rec.overhead_percent / 100
            cost += cost * rec.profit_percent / 100
            rec.total_cost = cost

    def _compute_rate_analysis_count(self):
        for rec in self:
            rec.rate_analysis_count = self.env['construction.rate.analysis.line'].search_count(
                [('resource_id', '=', rec.id)])

    def _compute_material_plan_count(self):
        for rec in self:
            rec.material_plan_count = self.env['construction.material.plan'].search_count(
                [('resource_id', '=', rec.id)])


class ConstructionResourceType(models.Model):
    _name = 'construction.resource.type'
    _description = 'Resource Type'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)
