from odoo import api, fields, models, _


class UtilityRegion(models.Model):
    _name = 'utility.region'
    _description = 'Service Region'
    _order = 'code, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    name = fields.Char(string='Region Name', required=True, index=True, tracking=True)
    code = fields.Char(string='Region Code', required=True, index=True, tracking=True)
    manager_id = fields.Many2one('res.users', string='Regional Manager', tracking=True)
    description = fields.Text(string='Description')

    area_ids = fields.One2many('utility.area', 'region_id', string='Service Areas')
    area_count = fields.Integer(string='Area Count', compute='_compute_area_count', store=True)
    customer_count = fields.Integer(string='Customer Count', compute='_compute_counts', store=True)
    meter_count = fields.Integer(string='Meter Count', compute='_compute_counts', store=True)

    _sql_constraints = [
        ('code_company_uniq', 'UNIQUE(code, company_id)', 'Region code must be unique per company!'),
    ]

    @api.depends('area_ids')
    def _compute_area_count(self):
        for rec in self:
            rec.area_count = len(rec.area_ids)

    @api.depends('area_ids.customer_count', 'area_ids.meter_count')
    def _compute_counts(self):
        for rec in self:
            rec.customer_count = sum(rec.area_ids.mapped('customer_count'))
            rec.meter_count = sum(rec.area_ids.mapped('meter_count'))

    def name_get(self):
        return [(rec.id, f'[{rec.code}] {rec.name}') for rec in self]
