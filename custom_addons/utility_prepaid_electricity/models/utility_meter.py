from odoo import api, fields, models, _


class UtilityMeter(models.Model):
    _name = 'utility.meter'
    _description = 'Electricity Meter'
    _order = 'meter_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'meter_number'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)

    meter_number = fields.Char(string='Meter Number', required=True, index=True, copy=False, tracking=True)
    serial_number = fields.Char(string='Serial Number', index=True, tracking=True)
    manufacturer = fields.Char(string='Manufacturer', tracking=True)
    model = fields.Char(string='Model', tracking=True)
    firmware_version = fields.Char(string='Firmware Version')
    sts_key_revision = fields.Integer(string='STS Key Revision', default=2,
                                      help='STS key revision number for token generation')

    meter_type_id = fields.Many2one('utility.meter.type', string='Meter Type', required=True, tracking=True)
    status_id = fields.Many2one('utility.meter.status', string='Status', required=True, index=True, tracking=True)

    phase = fields.Selection([
        ('single', 'Single Phase'),
        ('three', 'Three Phase'),
    ], string='Phase', required=True, default='single')
    voltage = fields.Char(string='Voltage Rating')
    current_rating = fields.Char(string='Current Rating')
    power_rating = fields.Float(string='Power Rating (kW)')

    installation_date = fields.Date(string='Installation Date', tracking=True)
    last_read_date = fields.Datetime(string='Last Reading Date')

    gps_latitude = fields.Float(string='GPS Latitude', digits=(10, 7))
    gps_longitude = fields.Float(string='GPS Longitude', digits=(10, 7))

    sim_number = fields.Char(string='SIM Number', index=True)
    communication_type = fields.Selection([
        ('gsm', 'GSM/GPRS'),
        ('nbiot', 'NB-IoT'),
        ('lora', 'LoRaWAN'),
        ('rf', 'RF Mesh'),
        ('plc', 'PLC'),
        ('manual', 'Manual Reading'),
    ], string='Communication Type', default='manual')

    account_id = fields.Many2one('utility.account', string='Account', index=True, tracking=True)
    customer_id = fields.Many2one('utility.customer', related='account_id.customer_id', store=True, index=True)
    region_id = fields.Many2one('utility.region', string='Region', index=True, tracking=True)
    area_id = fields.Many2one('utility.area', string='Service Area', index=True, tracking=True)
    feeder_id = fields.Many2one('utility.feeder', string='Feeder', index=True, tracking=True)
    transformer_id = fields.Many2one('utility.transformer', string='Transformer', index=True, tracking=True)

    sale_ids = fields.One2many('utility.sale', 'meter_id', string='Sales')
    alarm_ids = fields.One2many('utility.alarm', 'meter_id', string='Alarms')

    sale_count = fields.Integer(string='Sale Count', compute='_compute_sale_count', store=True)
    last_sale_date = fields.Datetime(string='Last Sale Date', compute='_compute_last_sale', store=True)

    _sql_constraints = [
        ('meter_number_uniq', 'UNIQUE(meter_number, company_id)', 'Meter number must be unique per company!'),
        ('serial_number_uniq', 'UNIQUE(serial_number)', 'Serial number must be unique!'),
    ]

    @api.depends('sale_ids')
    def _compute_sale_count(self):
        for rec in self:
            rec.sale_count = len(rec.sale_ids)

    @api.depends('sale_ids', 'sale_ids.date')
    def _compute_last_sale(self):
        for rec in self:
            last = rec.sale_ids.sorted('date', reverse=True)[:1]
            rec.last_sale_date = last.date if last else False

    def name_get(self):
        return [(rec.id, rec.meter_number) for rec in self]

    @api.model
    def create(self, vals):
        if not vals.get('meter_number') or vals.get('meter_number') == _('New'):
            vals['meter_number'] = self.env['ir.sequence'].next_by_code('utility.meter') or _('New')
        return super().create(vals)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100):
        args = list(args or [])
        if name:
            args = ['|', ('meter_number', operator, name),
                    ('serial_number', operator, name)] + args
        return super()._search(args, limit=limit)
