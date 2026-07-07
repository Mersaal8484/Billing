from odoo import api, fields, models, _


class UtilityArea(models.Model):
    _name = 'utility.area'
    _description = 'Service Area'
    _order = 'code, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='region_id.company_id', store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    name = fields.Char(string='Area Name', required=True, index=True, tracking=True)
    code = fields.Char(string='Area Code', required=True, index=True, tracking=True)
    region_id = fields.Many2one('utility.region', string='Region', required=True, index=True, tracking=True)
    manager_id = fields.Many2one('res.users', string='Area Manager', tracking=True)
    description = fields.Text(string='Description')

    feeder_ids = fields.One2many('utility.feeder', 'area_id', string='Feeders')
    transformer_ids = fields.One2many('utility.transformer', 'area_id', string='Transformers')
    customer_ids = fields.One2many('utility.customer', 'area_id', string='Customers')

    feeder_count = fields.Integer(string='Feeder Count', compute='_compute_counts', store=True)
    transformer_count = fields.Integer(string='Transformer Count', compute='_compute_counts', store=True)
    customer_count = fields.Integer(string='Customer Count', compute='_compute_counts', store=True)
    meter_count = fields.Integer(string='Meter Count', compute='_compute_counts', store=True)

    _sql_constraints = [
        ('code_region_uniq', 'UNIQUE(code, region_id)', 'Area code must be unique per region!'),
    ]

    @api.depends('region_id', 'feeder_ids', 'transformer_ids', 'customer_ids')
    def _compute_counts(self):
        for rec in self:
            rec.feeder_count = len(rec.feeder_ids)
            rec.transformer_count = len(rec.transformer_ids)
            rec.customer_count = len(rec.customer_ids)
            rec.meter_count = sum(rec.customer_ids.mapped('meter_count'))

    def name_get(self):
        return [(rec.id, f'[{rec.code}] {rec.name}') for rec in self]
