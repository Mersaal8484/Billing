from odoo import api, fields, models


class UtilityFeeder(models.Model):
    _name = 'utility.feeder'
    _description = 'Utility Feeder'
    _order = 'name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('Feeder Name', required=True)
    code = fields.Char('Feeder Code', required=True)
    zone_id = fields.Many2one('utility.region', 'Zone', domain="[('type', '=', 'zone')]")
    area_id = fields.Many2one('utility.region', 'Area', related='zone_id.parent_id', store=True)
    region_id = fields.Many2one('utility.region', 'Region', related='zone_id.parent_id.parent_id', store=True)
    voltage_level = fields.Selection([
        ('lv', 'Low Voltage'),
        ('mv', 'Medium Voltage'),
        ('hv', 'High Voltage'),
    ], string='Voltage Level')
    rated_capacity = fields.Float('Rated Capacity (kVA)')
    current_load = fields.Float('Current Load (kVA)')
    load_percentage = fields.Float('Load %', compute='_compute_load_percentage', store=True)
    substation_id = fields.Many2one('utility.substation', 'Substation')
    transformer_ids = fields.One2many('utility.transformer', 'feeder_id', string='Transformers')
    meter_ids = fields.One2many('utility.meter', 'feeder_id', string='Meters')

    _sql_constraints = [
        ('unique_feeder_code_zone', 'unique(code, zone_id)', 'Feeder code must be unique per zone!'),
    ]

    @api.depends('current_load', 'rated_capacity')
    def _compute_load_percentage(self):
        for r in self:
            if r.rated_capacity:
                r.load_percentage = (r.current_load / r.rated_capacity) * 100.0
            else:
                r.load_percentage = 0.0
