from odoo import api, fields, models, _


class UtilityMeter(models.Model):
    _name = 'utility.meter'
    _description = 'Utility Meter'
    _inherit = ['mail.thread']
    _order = 'meter_number'
    _rec_name = 'meter_number'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    meter_number = fields.Char('Meter Number', required=True, index=True, default=lambda self: _('New'))
    serial_number = fields.Char('Serial Number', index=True)
    manufacturer = fields.Char('Manufacturer')
    model_id = fields.Many2one('utility.meter.model', 'Model')
    payment_type = fields.Selection([
        ('postpaid', 'آجل الدفع (عن بُعد / ذكي)'),
        ('prepaid', 'دفع مسبق (Prepaid)'),
        ('manual', 'يدوي (Manual)')
    ], string='نظام العداد', default='manual', required=True)
    meter_type_id = fields.Many2one('utility.meter.type', 'Meter Type')
    status_id = fields.Many2one('utility.meter.status', 'Status')
    phase = fields.Selection([
        ('single', 'Single Phase'),
        ('three', 'Three Phase'),
    ], string='Phase')
    voltage = fields.Float('Voltage (V)')
    current_rating = fields.Float('Current Rating (A)')
    power_rating = fields.Float('Power Rating (kW)')
    sts_key_revision = fields.Char('STS Key Revision')
    customer_id = fields.Many2one('utility.customer', 'Customer/Contract', index=True)
    account_id = fields.Many2one('utility.customer', string='Account', related='customer_id', store=True)
    area_id = fields.Many2one('utility.region', 'Area', domain="[('type', '=', 'area')]")
    zone_id = fields.Many2one('utility.region', 'Zone', domain="[('type', '=', 'zone')]")
    region_id = fields.Many2one('utility.region', 'Region', related='area_id.parent_id', store=True)
    route_id = fields.Many2one('utility.route', 'Route', related='customer_id.route_id', store=True)
    feeder_id = fields.Many2one('utility.feeder', 'Feeder')
    transformer_id = fields.Many2one('utility.transformer', 'Transformer')
    substation_id = fields.Many2one('utility.substation', 'Substation')
    installation_date = fields.Date('Installation Date')
    address = fields.Text('Address')
    communication_type = fields.Selection([
        ('gsm', 'GSM'),
        ('nbiot', 'NB-IoT'),
        ('lora', 'LoRa'),
        ('rf', 'RF'),
        ('plc', 'PLC'),
        ('manual', 'Manual'),
    ], string='Communication Type')
    sim_number = fields.Char('SIM Number')
    last_read_date = fields.Datetime('Last Read Date')

    # خصائص الربط
    is_coupling_meter = fields.Boolean('عداد ربط رئيسي', default=False, help='يُشير إذا كان هذا العداد هو عداد ربط يقرأ إجمالي طاقة الفيدر أو المحطة')

    _sql_constraints = [
        ('unique_meter_number_company', 'unique(meter_number, company_id)',
         'Meter number must be unique per company!'),
        ('unique_serial_number', 'unique(serial_number)', 'Serial number must be unique!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('meter_number', _('New')) == _('New'):
                vals['meter_number'] = self.env['ir.sequence'].next_by_code('utility.meter') or _('New')
        return super().create(vals_list)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('meter_number', operator, name), ('serial_number', operator, name)]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)


class UtilityMeterType(models.Model):
    _name = 'utility.meter.type'
    _description = 'Utility Meter Type'
    _order = 'name'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    phase = fields.Selection([
        ('single', 'Single Phase'),
        ('three', 'Three Phase'),
    ], string='Phase')
    description = fields.Text('Description')


class UtilityMeterModel(models.Model):
    _name = 'utility.meter.model'
    _description = 'Utility Meter Model'
    _order = 'name'

    name = fields.Char('Model Name', required=True)
    code = fields.Char('Model Code', required=True)
    manufacturer = fields.Char('Manufacturer')
    meter_type_id = fields.Many2one('utility.meter.type', 'Meter Type')
    phase = fields.Selection([
        ('single', 'Single Phase'),
        ('three', 'Three Phase'),
    ], string='Phase')
    voltage_range = fields.Char('Voltage Range')
    current_range = fields.Char('Current Range')
    sts_supported = fields.Boolean('STS Supported')
    communication_types = fields.Char('Communication Types')
    description = fields.Text('Description')


class UtilityMeterStatus(models.Model):
    _name = 'utility.meter.status'
    _description = 'Utility Meter Status'
    _order = 'sequence, name'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    sequence = fields.Integer('Sequence')
    description = fields.Text('Description')
