from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConstructionBoqItem(models.Model):
    _name = 'construction.boq.item'
    _description = 'BOQ Item'
    _order = 'sequence, code'
    _check_company_auto = True
    _rec_name = 'display_name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='boq_id.company_id',
                                 store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project',
                                 related='boq_id.project_id', store=True, index=True)
    boq_id = fields.Many2one('construction.boq', string='BOQ',
                             required=True, ondelete='cascade', index=True)
    section_id = fields.Many2one('construction.boq.section', string='Section',
                                 index=True)

    code = fields.Char(string='Item Code', required=True, index=True)
    name = fields.Char(string='Description', required=True, translate=True)
    arabic_name = fields.Char(string='Arabic Description')
    sequence = fields.Integer(default=10)
    display_name = fields.Char(string='Display Name',
                               compute='_compute_display_name', store=True)
    description = fields.Text(string='Full Description', translate=True)

    parent_id = fields.Many2one('construction.boq.item', string='Parent Item',
                                index=True)
    child_ids = fields.One2many('construction.boq.item', 'parent_id',
                                string='Sub Items')
    level = fields.Integer(string='Level', compute='_compute_level', store=True)

    wbs_code = fields.Char(string='WBS Code', index=True)
    cost_code = fields.Char(string='Cost Code', index=True)
    activity_code = fields.Char(string='Activity Code', index=True)
    unit = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=0.0,
                            digits=(16, 3))
    rate = fields.Monetary(string='Rate', default=0.0)
    amount = fields.Monetary(string='Amount', compute='_compute_amount',
                             store=True)
    executed_quantity = fields.Float(string='Executed Quantity', default=0.0,
                                     digits=(16, 3))
    executed_percent = fields.Float(string='Executed %',
                                    compute='_compute_executed_percent',
                                    store=True, digits=(5, 2),
                                    group_operator='avg')
    remaining_quantity = fields.Float(string='Remaining Quantity',
                                      compute='_compute_remaining', store=True,
                                      digits=(16, 3))

    rate_analysis_ids = fields.One2many('construction.rate.analysis', 'boq_item_id',
                                        string='Rate Analysis')
    has_rate_analysis = fields.Boolean(string='Has Rate Analysis',
                                       compute='_compute_has_rate_analysis')

    material_plan_ids = fields.One2many('construction.material.plan', 'boq_item_id',
                                        string='Material Plans')
    variation_ids = fields.One2many('construction.variation.line', 'boq_item_id',
                                    string='Variations')
    progress_ids = fields.One2many('construction.progress.line', 'boq_item_id',
                                   string='Progress Records')
    ipc_line_ids = fields.One2many('construction.ipc.line', 'boq_item_id',
                                   string='IPC Lines')
    sale_order_line_ids = fields.One2many('sale.order.line',
        'construction_boq_item_id', string='Sale Order Lines')
    purchase_order_line_ids = fields.One2many('purchase.order.line',
        'construction_boq_item_id', string='Purchase Order Lines')

    note = fields.Text(string='Notes')
    internal_note = fields.Text(string='Internal Notes')

    _sql_constraints = [
        ('item_code_boq_unique', 'UNIQUE(code, boq_id, parent_id)',
         'Item code must be unique per BOQ!'),
        ('check_quantity_positive', 'CHECK(quantity >= 0)',
         'Quantity must be positive!'),
        ('check_rate_positive', 'CHECK(rate >= 0)',
         'Rate must be positive!'),
    ]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'[{rec.code}] {rec.name}'

    @api.depends('quantity', 'rate')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.quantity * rec.rate

    @api.depends('executed_quantity', 'quantity')
    def _compute_executed_percent(self):
        for rec in self:
            rec.executed_percent = (rec.executed_quantity / rec.quantity * 100) if rec.quantity else 0.0

    @api.depends('quantity', 'executed_quantity')
    def _compute_remaining(self):
        for rec in self:
            rec.remaining_quantity = rec.quantity - rec.executed_quantity

    @api.depends('parent_id')
    def _compute_level(self):
        for rec in self:
            level = 0
            parent = rec.parent_id
            while parent:
                level += 1
                parent = parent.parent_id
            rec.level = level

    def _compute_has_rate_analysis(self):
        for rec in self:
            rec.has_rate_analysis = bool(self.env['construction.rate.analysis'].search_count(
                [('boq_item_id', '=', rec.id)]))

    def action_open_rate_analysis(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rate Analysis'),
            'res_model': 'construction.rate.analysis',
            'view_mode': 'tree,form',
            'domain': [('boq_item_id', '=', self.id)],
            'context': {'default_boq_item_id': self.id},
        }

    def action_open_material_plan(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Plan'),
            'res_model': 'construction.material.plan',
            'view_mode': 'tree,form',
            'domain': [('boq_item_id', '=', self.id)],
            'context': {'default_boq_item_id': self.id},
        }

    @api.onchange('unit')
    def _onchange_unit_set_default_rate(self):
        if self.unit and not self.rate:
            product = self.env['product.product'].search([
                ('uom_id', '=', self.unit.id)], limit=1)
            if product:
                self.rate = product.standard_price
