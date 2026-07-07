from odoo import api, fields, models, _


class UtilityTransformer(models.Model):
    _name = 'utility.transformer'
    _description = 'Distribution Transformer'
    _order = 'code, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='area_id.company_id', store=True, index=True)

    name = fields.Char(string='Transformer Name', required=True, index=True, tracking=True)
    code = fields.Char(string='Transformer Code', required=True, index=True, tracking=True)
    area_id = fields.Many2one('utility.area', string='Service Area', required=True, index=True, tracking=True)
    region_id = fields.Many2one('utility.region', related='area_id.region_id', store=True, index=True)
    feeder_id = fields.Many2one('utility.feeder', string='Feeder', index=True, tracking=True)

    manufacturer = fields.Char(string='Manufacturer')
    model = fields.Char(string='Model')
    serial_number = fields.Char(string='Serial Number', index=True)
    year_manufactured = fields.Integer(string='Year Manufactured')
    installation_date = fields.Date(string='Installation Date')

    capacity = fields.Float(string='Capacity (kVA)', required=True)
    voltage_primary = fields.Char(string='Primary Voltage')
    voltage_secondary = fields.Char(string='Secondary Voltage')
    phase = fields.Selection([
        ('single', 'Single Phase'),
        ('three', 'Three Phase'),
    ], string='Phase', default='three', required=True)
    current_load = fields.Float(string='Current Load (kVA)')
    load_percentage = fields.Float(string='Load %', compute='_compute_load_percentage', store=True, digits=(5, 2))

    gps_latitude = fields.Float(string='GPS Latitude', digits=(10, 7))
    gps_longitude = fields.Float(string='GPS Longitude', digits=(10, 7))

    rtu_ids = fields.One2many('utility.rtu', 'transformer_id', string='RTUs')
    meter_ids = fields.One2many('utility.meter', 'transformer_id', string='Meters')
    meter_count = fields.Integer(string='Meter Count', compute='_compute_meter_count', store=True)

    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('fault', 'Fault'),
        ('maintenance', 'Under Maintenance'),
        ('decommissioned', 'Decommissioned'),
    ], string='Status', default='active', index=True, tracking=True)

    _sql_constraints = [
        ('code_area_uniq', 'UNIQUE(code, area_id)', 'Transformer code must be unique per area!'),
    ]

    @api.depends('capacity', 'current_load')
    def _compute_load_percentage(self):
        for rec in self:
            if rec.capacity and rec.capacity > 0:
                rec.load_percentage = (rec.current_load or 0.0) / rec.capacity * 100
            else:
                rec.load_percentage = 0.0

    @api.depends('meter_ids')
    def _compute_meter_count(self):
        for rec in self:
            rec.meter_count = len(rec.meter_ids)

    def name_get(self):
        return [(rec.id, f'[{rec.code}] {rec.name}') for rec in self]
