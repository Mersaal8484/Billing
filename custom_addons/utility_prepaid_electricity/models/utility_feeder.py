from odoo import api, fields, models, _


class UtilityFeeder(models.Model):
    _name = 'utility.feeder'
    _description = 'Electrical Feeder'
    _order = 'code, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='area_id.company_id', store=True, index=True)

    name = fields.Char(string='Feeder Name', required=True, index=True, tracking=True)
    code = fields.Char(string='Feeder Code', required=True, index=True, tracking=True)
    area_id = fields.Many2one('utility.area', string='Service Area', required=True, index=True, tracking=True)
    region_id = fields.Many2one('utility.region', related='area_id.region_id', store=True, index=True)

    voltage_level = fields.Selection([
        ('lv', 'Low Voltage (<1kV)'),
        ('mv', 'Medium Voltage (1kV-33kV)'),
        ('hv', 'High Voltage (>33kV)'),
    ], string='Voltage Level', default='lv', required=True)
    rated_capacity = fields.Float(string='Rated Capacity (kVA)')
    current_load = fields.Float(string='Current Load (kVA)')
    load_percentage = fields.Float(string='Load %', compute='_compute_load', store=True, digits=(5, 2))

    rtu_ids = fields.One2many('utility.rtu', 'feeder_id', string='RTUs')
    transformer_ids = fields.One2many('utility.transformer', 'feeder_id', string='Transformers')
    meter_ids = fields.One2many('utility.meter', 'feeder_id', string='Meters')

    transformer_count = fields.Integer(string='Transformer Count', compute='_compute_counts', store=True)
    meter_count = fields.Integer(string='Meter Count', compute='_compute_counts', store=True)

    _sql_constraints = [
        ('code_area_uniq', 'UNIQUE(code, area_id)', 'Feeder code must be unique per area!'),
    ]

    @api.depends('rated_capacity', 'current_load')
    def _compute_load(self):
        for rec in self:
            if rec.rated_capacity and rec.rated_capacity > 0:
                rec.load_percentage = (rec.current_load or 0.0) / rec.rated_capacity * 100
            else:
                rec.load_percentage = 0.0

    @api.depends('transformer_ids', 'meter_ids')
    def _compute_counts(self):
        for rec in self:
            rec.transformer_count = len(rec.transformer_ids)
            rec.meter_count = len(rec.meter_ids)

    def name_get(self):
        return [(rec.id, f'[{rec.code}] {rec.name}') for rec in self]
