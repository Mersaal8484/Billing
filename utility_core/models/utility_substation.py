from odoo import api, fields, models


class UtilitySubstation(models.Model):
    _name = 'utility.substation'
    _description = 'محطة فرعية'
    _order = 'name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('Substation Name', required=True)
    code = fields.Char('Substation Code', required=True)
    zone_id = fields.Many2one('utility.region', 'Zone', domain="[('type', '=', 'zone')]")
    area_id = fields.Many2one('utility.region', 'Area', related='zone_id.parent_id', store=True)
    region_id = fields.Many2one('utility.region', 'Region', related='zone_id.parent_id.parent_id', store=True)
    voltage_level = fields.Selection([
        ('lv', 'Low Voltage'),
        ('mv', 'Medium Voltage'),
        ('hv', 'High Voltage'),
    ], string='مستوى الجهد')
    capacity_kva = fields.Float('Capacity (kVA)')
    address = fields.Text('Address')
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('fault', 'Fault'),
        ('maintenance', 'Maintenance'),
    ], string='الحالة', default='active')
    feeder_ids = fields.One2many('utility.feeder', 'substation_id', string='المغذيات')
    transformer_ids = fields.One2many('utility.transformer', 'substation_id', string='المحولات')

    _sql_constraints = [
        ('unique_substation_code_zone', 'unique(code, zone_id)', 'Substation code must be unique per zone!'),
    ]
