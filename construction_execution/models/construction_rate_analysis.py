from odoo import api, fields, models


class ConstructionRateAnalysis(models.Model):
    _name = 'construction.rate.analysis'
    _description = 'Rate Analysis'
    _order = 'boq_item_id, sequence'
    _check_company_auto = True
    _rec_name = 'display_name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='boq_item_id.company_id',
                                 store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    boq_item_id = fields.Many2one('construction.boq.item', string='BOQ Item',
                                  required=True, index=True)
    project_id = fields.Many2one('construction.project',
                                 related='boq_item_id.project_id', store=True)
    name = fields.Char(string='Analysis Name', compute='_compute_name', store=True)
    display_name = fields.Char(string='Display Name', compute='_compute_name',
                               store=True)
    sequence = fields.Integer(default=10)
    date = fields.Date(string='Date', default=fields.Date.today)
    version = fields.Char(string='Version', default='1.0')

    direct_cost = fields.Monetary(string='Direct Cost',
                                  compute='_compute_costs', store=True)
    indirect_cost = fields.Monetary(string='Indirect Cost',
                                    compute='_compute_costs', store=True)
    total_cost = fields.Monetary(string='Total Cost',
                                 compute='_compute_costs', store=True)
    markup_percent = fields.Float(string='Markup %', default=5.0,
                                  digits=(5, 2))
    profit_percent = fields.Float(string='Profit %', default=10.0,
                                  digits=(5, 2))
    markup_amount = fields.Monetary(string='Markup Amount',
                                    compute='_compute_costs', store=True)
    profit_amount = fields.Monetary(string='Profit Amount',
                                    compute='_compute_costs', store=True)
    final_rate = fields.Monetary(string='Final Rate',
                                 compute='_compute_costs', store=True)

    line_ids = fields.One2many('construction.rate.analysis.line', 'rate_analysis_id',
                               string='Analysis Lines', copy=True)
    line_count = fields.Integer(string='Line Count',
                                compute='_compute_line_count', store=True)

    note = fields.Text(string='Notes')

    @api.depends('boq_item_id', 'boq_item_id.code', 'boq_item_id.name')
    def _compute_name(self):
        for rec in self:
            item = rec.boq_item_id
            rec.name = f'Rate Analysis - {item.code} {item.name}' if item else 'Rate Analysis'
            rec.display_name = rec.name

    @api.depends('line_ids.total_cost', 'markup_percent', 'profit_percent')
    def _compute_costs(self):
        for rec in self:
            direct = sum(rec.line_ids.filtered(
                lambda l: l.resource_type in ('material', 'labor', 'equipment', 'subcontract')
            ).mapped('total_cost'))
            indirect = sum(rec.line_ids.filtered(
                lambda l: l.resource_type == 'overhead'
            ).mapped('total_cost'))
            rec.direct_cost = direct
            rec.indirect_cost = indirect
            base_cost = direct + indirect
            rec.total_cost = base_cost
            rec.markup_amount = base_cost * rec.markup_percent / 100
            rec.profit_amount = (base_cost + rec.markup_amount) * rec.profit_percent / 100
            rec.final_rate = base_cost + rec.markup_amount + rec.profit_amount

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def action_calculate(self):
        self._compute_costs()

    def action_apply_rate(self):
        self.ensure_one()
        item = self.boq_item_id
        if item:
            item.write({'rate': self.final_rate})


class ConstructionRateAnalysisLine(models.Model):
    _name = 'construction.rate.analysis.line'
    _description = 'Rate Analysis Line'
    _order = 'rate_analysis_id, sequence'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company',
                                 related='rate_analysis_id.company_id',
                                 store=True, index=True)
    currency_id = fields.Many2one('res.currency',
                                  related='company_id.currency_id')
    rate_analysis_id = fields.Many2one('construction.rate.analysis',
                                       string='Rate Analysis',
                                       required=True, ondelete='cascade',
                                       index=True)
    boq_item_id = fields.Many2one('construction.boq.item',
                                  related='rate_analysis_id.boq_item_id',
                                  store=True, index=True)
    sequence = fields.Integer(default=10)
    resource_id = fields.Many2one('construction.resource',
                                  string='Resource', required=True)
    resource_type = fields.Selection([
        ('material', 'Material'),
        ('labor', 'Labor'),
        ('equipment', 'Equipment'),
        ('subcontract', 'Subcontract'),
        ('overhead', 'Overhead'),
        ('profit', 'Profit'),
        ('miscellaneous', 'Miscellaneous'),
    ], string='Resource Type', required=True, default='material')
    name = fields.Char(string='Description', compute='_compute_name', store=True)
    uom_id = fields.Many2one('uom.uom', string='Unit',
                             related='resource_id.uom_id', store=True)
    quantity = fields.Float(string='Quantity', default=1.0, digits=(16, 3))
    unit_cost = fields.Monetary(string='Unit Cost', default=0.0)
    total_cost = fields.Monetary(string='Total Cost',
                                 compute='_compute_total_cost', store=True)
    wastage_percent = fields.Float(string='Wastage %', default=0.0,
                                   digits=(5, 2))
    net_quantity = fields.Float(string='Net Quantity',
                                compute='_compute_net_quantity', store=True,
                                digits=(16, 3))
    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('check_qty_positive', 'CHECK(quantity >= 0)', 'Quantity must be positive!'),
    ]

    @api.depends('resource_id', 'resource_id.name')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.resource_id.name if rec.resource_id else ''

    @api.depends('quantity', 'unit_cost', 'wastage_percent')
    def _compute_total_cost(self):
        for rec in self:
            qty = rec.quantity
            rec.net_quantity = qty * (1 + rec.wastage_percent / 100)
            rec.total_cost = rec.net_quantity * rec.unit_cost

    @api.depends('quantity', 'wastage_percent')
    def _compute_net_quantity(self):
        for rec in self:
            rec.net_quantity = rec.quantity * (1 + rec.wastage_percent / 100)

    @api.onchange('resource_id')
    def _onchange_resource(self):
        if self.resource_id:
            self.resource_type = dict(self.resource_id.fields_get(
                ['resource_type'])['resource_type']['selection']).get(
                self.resource_id.resource_type, 'miscellaneous')
            self.unit_cost = self.resource_id.unit_cost
            self.uom_id = self.resource_id.uom_id.id
