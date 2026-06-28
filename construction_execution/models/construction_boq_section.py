from odoo import api, fields, models


class ConstructionBoqSection(models.Model):
    _name = 'construction.boq.section'
    _description = 'BOQ Section'
    _order = 'sequence, code'
    _check_company_auto = True
    _rec_name = 'display_name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='boq_id.company_id',
                                 store=True, index=True)
    boq_id = fields.Many2one('construction.boq', string='BOQ',
                             required=True, ondelete='cascade', index=True)
    project_id = fields.Many2one('construction.project',
                                 related='boq_id.project_id', store=True, index=True)
    parent_id = fields.Many2one('construction.boq.section', string='Parent Section',
                                index=True)
    child_ids = fields.One2many('construction.boq.section', 'parent_id',
                                string='Child Sections')
    code = fields.Char(string='Section Code', required=True, index=True)
    name = fields.Char(string='Name', required=True, translate=True)
    arabic_name = fields.Char(string='Arabic Name')
    sequence = fields.Integer(default=10)
    display_name = fields.Char(string='Display Name',
                               compute='_compute_display_name', store=True)
    description = fields.Text(string='Description', translate=True)

    wbs_code = fields.Char(string='WBS Code')
    cost_code = fields.Char(string='Cost Code')
    activity_code = fields.Char(string='Activity Code')

    item_ids = fields.One2many('construction.boq.item', 'section_id',
                               string='Items')
    item_count = fields.Integer(string='Item Count',
                                compute='_compute_item_count', store=True)
    total_quantity = fields.Float(string='Total Quantity',
                                  compute='_compute_totals', store=True,
                                  digits=(16, 3))
    total_amount = fields.Monetary(string='Total Amount',
                                   compute='_compute_totals', store=True)

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    _sql_constraints = [
        ('section_code_boq_unique', 'UNIQUE(code, boq_id)',
         'Section code must be unique per BOQ!'),
    ]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'[{rec.code}] {rec.name}'

    @api.depends('item_ids.quantity', 'item_ids.amount')
    def _compute_totals(self):
        for rec in self:
            items = rec.item_ids
            rec.total_quantity = sum(items.mapped('quantity'))
            rec.total_amount = sum(items.mapped('amount'))

    @api.depends('item_ids')
    def _compute_item_count(self):
        for rec in self:
            rec.item_count = len(rec.item_ids)
