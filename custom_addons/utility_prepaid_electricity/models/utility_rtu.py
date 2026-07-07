from odoo import api, fields, models, _


class UtilityRtu(models.Model):
    _name = 'utility.rtu'
    _description = 'Remote Terminal Unit (RTU)'
    _order = 'code, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)

    name = fields.Char(string='RTU Name', required=True, index=True, tracking=True)
    code = fields.Char(string='RTU Code', required=True, index=True, tracking=True)
    serial_number = fields.Char(string='Serial Number', index=True, tracking=True)
    manufacturer = fields.Char(string='Manufacturer', tracking=True)
    model = fields.Char(string='Model', tracking=True)
    firmware_version = fields.Char(string='Firmware Version')

    rtu_type = fields.Selection([
        ('feeder', 'Feeder RTU'),
        ('transformer', 'Transformer RTU'),
        ('substation', 'Substation RTU'),
        ('capacitor', 'Capacitor Bank RTU'),
        ('recloser', 'Recloser RTU'),
        ('other', 'Other'),
    ], string='RTU Type', required=True, default='feeder', tracking=True)

    communication_type = fields.Selection([
        ('gprs', 'GPRS/3G/4G'),
        ('fiber', 'Fiber Optic'),
        ('radio', 'Radio'),
        ('satellite', 'Satellite'),
        ('ethernet', 'Ethernet'),
        ('plc', 'Power Line Carrier'),
    ], string='Communication Type', default='gprs', required=True)

    protocol = fields.Selection([
        ('dnp3', 'DNP3'),
        ('iec104', 'IEC 60870-5-104'),
        ('iec101', 'IEC 60870-5-101'),
        ('modbus', 'Modbus RTU/TCP'),
        ('mqtt', 'MQTT'),
        ('opcua', 'OPC UA'),
    ], string='Protocol', default='dnp3', required=True)

    ip_address = fields.Char(string='IP Address')
    port = fields.Integer(string='Port', default=502)
    sim_number = fields.Char(string='SIM Number', index=True)

    feeder_id = fields.Many2one('utility.feeder', string='Feeder', index=True, tracking=True)
    transformer_id = fields.Many2one('utility.transformer', string='Transformer', index=True, tracking=True)
    area_id = fields.Many2one('utility.area', related='feeder_id.area_id', store=True, index=True)
    region_id = fields.Many2one('utility.region', related='area_id.region_id', store=True, index=True)

    gps_latitude = fields.Float(string='GPS Latitude', digits=(10, 7))
    gps_longitude = fields.Float(string='GPS Longitude', digits=(10, 7))

    status = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('fault', 'Fault'),
        ('maintenance', 'Under Maintenance'),
        ('decommissioned', 'Decommissioned'),
    ], string='Status', default='offline', index=True, tracking=True, required=True)

    last_communication = fields.Datetime(string='Last Communication')
    signal_strength = fields.Integer(string='Signal Strength (%)', digits=(3, 0))
    battery_level = fields.Integer(string='Battery Level (%)', digits=(3, 0))
    uptime_days = fields.Integer(string='Uptime (Days)')

    installation_date = fields.Date(string='Installation Date')
    last_maintenance_date = fields.Date(string='Last Maintenance Date')

    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_company_uniq', 'UNIQUE(code, company_id)', 'RTU code must be unique per company!'),
        ('serial_uniq', 'UNIQUE(serial_number)', 'Serial number must be unique!'),
    ]

    def name_get(self):
        return [(rec.id, f'[{rec.code}] {rec.name}') for rec in self]

    def action_online(self):
        self.write({'status': 'online', 'last_communication': fields.Datetime.now()})

    def action_offline(self):
        self.write({'status': 'offline'})

    def action_maintenance(self):
        self.write({'status': 'maintenance'})

    def action_decommission(self):
        self.write({'status': 'decommissioned'})
