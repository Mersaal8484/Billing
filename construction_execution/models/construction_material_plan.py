from odoo import api, fields, models


class ConstructionMaterialPlan(models.Model):
    _name = 'construction.material.plan'
    _description = 'Material Plan'
    _order = 'boq_item_id, date'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='boq_item_id.company_id',
                                 store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project',
                                 related='boq_item_id.project_id', store=True, index=True)
    boq_item_id = fields.Many2one('construction.boq.item', string='BOQ Item',
                                  required=True, index=True)
    resource_id = fields.Many2one('construction.resource', string='Resource',
                                  required=True, index=True)
    product_id = fields.Many2one('product.product', string='Product',
                                 related='resource_id.product_id', store=True)
    uom_id = fields.Many2one('uom.uom', string='Unit',
                             related='resource_id.uom_id', store=True)

    name = fields.Char(string='Description', compute='_compute_name', store=True)
    date = fields.Date(string='Planned Date', required=True)
    planned_quantity = fields.Float(string='Planned Quantity', required=True,
                                    default=0.0, digits=(16, 3))
    executed_quantity = fields.Float(string='Executed Quantity', default=0.0,
                                     digits=(16, 3))
    remaining_quantity = fields.Float(string='Remaining Quantity',
                                      compute='_compute_remaining', store=True,
                                      digits=(16, 3))
    unit_cost = fields.Monetary(string='Unit Cost', default=0.0)
    planned_cost = fields.Monetary(string='Planned Cost',
                                   compute='_compute_costs', store=True)
    actual_cost = fields.Monetary(string='Actual Cost', default=0.0)

    state = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('delayed', 'Delayed'),
    ], string='Status', default='planned', index=True)

    request_ids = fields.One2many('construction.material.request.line',
                                  'material_plan_id', string='Material Requests')
    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('check_qty_positive', 'CHECK(planned_quantity >= 0)',
         'Planned quantity must be positive!'),
    ]

    @api.depends('boq_item_id', 'resource_id')
    def _compute_name(self):
        for rec in self:
            rec.name = f'{rec.boq_item_id.name} - {rec.resource_id.name}' if rec.boq_item_id and rec.resource_id else ''

    @api.depends('planned_quantity', 'executed_quantity')
    def _compute_remaining(self):
        for rec in self:
            rec.remaining_quantity = rec.planned_quantity - rec.executed_quantity

    @api.depends('planned_quantity', 'unit_cost')
    def _compute_costs(self):
        for rec in self:
            rec.planned_cost = rec.planned_quantity * rec.unit_cost
