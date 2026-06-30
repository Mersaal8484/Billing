from odoo import api, fields, models, _


class UtilityConnection(models.Model):
    _name = 'utility.connection'
    _description = 'Utility Connection'
    _order = 'id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('Connection Number', default=lambda self: _('New'))
    customer_id = fields.Many2one('utility.customer', 'Customer', required=True)
    account_id = fields.Many2one('utility.customer', 'Account', related='customer_id', store=True)
    connection_type = fields.Many2one('utility.connection.type', 'Connection Type')
    meter_id = fields.Many2one('utility.meter', 'Meter')
    connection_date = fields.Date('Connection Date')
    status = fields.Selection([
        ('active', 'Active'),
        ('disconnected', 'Disconnected'),
        ('suspended', 'Suspended'),
    ], string='Status', default='active')
    address = fields.Text('Address')
    gps_latitude = fields.Float('GPS Latitude')
    gps_longitude = fields.Float('GPS Longitude')
    notes = fields.Text('Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.connection') or _('New')
        return super().create(vals_list)


class UtilityConnectionType(models.Model):
    _name = 'utility.connection.type'
    _description = 'Utility Connection Type'
    _order = 'name'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    voltage_level = fields.Selection([
        ('lv', 'Low Voltage'),
        ('mv', 'Medium Voltage'),
        ('hv', 'High Voltage'),
    ], string='Voltage Level')
    phase = fields.Selection([
        ('single', 'Single Phase'),
        ('three', 'Three Phase'),
    ], string='Phase')
    description = fields.Text('Description')

