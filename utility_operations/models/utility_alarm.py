from odoo import api, fields, models, _


class UtilityAlarm(models.Model):
    _name = 'utility.alarm'
    _description = 'Utility Alarm'
    _rec_name = 'alarm_code'
    _order = 'alarm_date desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    alarm_code = fields.Char('Alarm Code', required=True, index=True, default=lambda self: _('New'))
    alarm_date = fields.Datetime('Alarm Date', default=fields.Datetime.now)
    alarm_type = fields.Selection([
        ('low_credit', 'Low Credit'),
        ('zero_credit', 'Zero Credit'),
        ('tamper', 'Tamper'),
        ('power_failure', 'Power Failure'),
        ('comm_failure', 'Communication Failure'),
        ('battery', 'Battery Low'),
        ('reverse_energy', 'Reverse Energy'),
        ('magnetic', 'Magnetic Tamper'),
        ('over_voltage', 'Over Voltage'),
        ('under_voltage', 'Under Voltage'),
        ('over_current', 'Over Current'),
        ('phase_failure', 'Phase Failure'),
        ('other', 'Other'),
    ], string='Alarm Type', required=True)
    severity = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('emergency', 'Emergency'),
    ], string='Severity', default='warning')
    customer_id = fields.Many2one('utility.customer', 'Customer')
    account_id = fields.Many2one('utility.customer', 'Account', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'Meter')
    area_id = fields.Many2one('utility.region', 'Area', domain="[('type', '=', 'area')]")
    region_id = fields.Many2one('utility.region', 'Region', related='area_id.parent_id', store=True)
    description = fields.Text('Description', required=True)
    meter_reading = fields.Float('Meter Reading')
    voltage = fields.Float('Voltage (V)')
    current = fields.Float('Current (A)')
    power = fields.Float('Power (kW)')
    state = fields.Selection([
        ('new', 'New'),
        ('acknowledged', 'Acknowledged'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ], string='State', default='new')
    assigned_to = fields.Many2one('res.users', 'Assigned To')
    resolution = fields.Text('Resolution')
    resolved_date = fields.Datetime('Resolved Date')
    service_order_id = fields.Many2one('utility.service.order', 'Service Order')

    def action_acknowledge(self):
        self.state = 'acknowledged'

    def action_start(self):
        self.state = 'in_progress'

    def action_resolve(self):
        self.state = 'resolved'
        self.resolved_date = fields.Datetime.now()

    def action_close(self):
        self.state = 'closed'

    def action_create_service_order(self):
        self.ensure_one()
        order = self.env['utility.service.order'].create({
            'service_type': 'tamper_investigation' if self.alarm_type == 'tamper' else 'maintenance',
            'description': self.description,
            'customer_id': self.customer_id.id,
            'account_id': self.account_id.id,
            'meter_id': self.meter_id.id,
            'priority': 'urgent' if self.severity in ('critical', 'emergency') else 'high',
        })
        self.service_order_id = order.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'utility.service.order',
            'res_id': order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def cron_check_low_credit(self):
        accounts = self.env['utility.customer'].search([('balance', '<', 50.0)])
        for account in accounts:
            existing = self.search([
                ('account_id', '=', account.id),
                ('alarm_type', '=', 'low_credit'),
                ('state', 'not in', ('resolved', 'closed')),
            ], limit=1)
            if existing:
                continue
            self.create({
                'alarm_type': 'low_credit',
                'severity': 'critical' if account.balance == 0 else 'warning',
                'description': _('Account %s has low balance: %s') % (account.customer_number, account.balance),
                'customer_id': account.id,
                'account_id': account.id,
                'meter_id': account.meter_id.id,
                'region_id': account.region_id.id,
                'area_id': account.area_id.id,
            })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('alarm_code', _('New')) == _('New'):
                vals['alarm_code'] = self.env['ir.sequence'].next_by_code('utility.alarm') or _('New')
        return super().create(vals_list)
