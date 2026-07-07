from odoo import api, fields, models, _


class UtilityAlarm(models.Model):
    _name = 'utility.alarm'
    _description = 'Meter Alarm / Event'
    _order = 'alarm_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'alarm_code'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)

    alarm_code = fields.Char(string='Alarm Code', required=True, index=True, copy=False,
                             default=lambda self: _('New'))
    alarm_date = fields.Datetime(string='Alarm Date', default=fields.Datetime.now, required=True, index=True)

    alarm_type = fields.Selection([
        ('low_credit', 'Low Credit'),
        ('zero_credit', 'Zero Credit'),
        ('tamper', 'Meter Tamper'),
        ('power_failure', 'Power Failure'),
        ('comm_failure', 'Communication Failure'),
        ('battery', 'Battery Low'),
        ('reverse_energy', 'Reverse Energy'),
        ('magnetic', 'Magnetic Detection'),
        ('over_voltage', 'Over Voltage'),
        ('under_voltage', 'Under Voltage'),
        ('over_current', 'Over Current'),
        ('phase_failure', 'Phase Failure'),
        ('other', 'Other'),
    ], string='Alarm Type', required=True, index=True, tracking=True)

    severity = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('emergency', 'Emergency'),
    ], string='Severity', default='warning', index=True, required=True)

    customer_id = fields.Many2one('utility.customer', string='Customer', index=True, tracking=True)
    account_id = fields.Many2one('utility.account', string='Account', index=True, tracking=True)
    meter_id = fields.Many2one('utility.meter', string='Meter', index=True, tracking=True)
    region_id = fields.Many2one('utility.region', string='Region', index=True)
    area_id = fields.Many2one('utility.area', string='Area', index=True)

    description = fields.Text(string='Description', required=True)
    meter_reading = fields.Float(string='Meter Reading at Event', digits=(16, 2))
    voltage = fields.Float(string='Voltage')
    current = fields.Float(string='Current')
    power = fields.Float(string='Power (kW)')

    state = fields.Selection([
        ('new', 'New'),
        ('acknowledged', 'Acknowledged'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ], string='Status', default='new', index=True, tracking=True, required=True)

    assigned_to = fields.Many2one('res.users', string='Assigned To', tracking=True)
    resolution = fields.Text(string='Resolution')
    resolved_date = fields.Datetime(string='Resolved Date')
    closed_date = fields.Datetime(string='Closed Date')

    service_order_id = fields.Many2one('utility.service.order', string='Related Service Order',
                                       index=True)

    _sql_constraints = [
        ('check_alarm_dates', 'CHECK(resolved_date IS NULL OR alarm_date <= resolved_date)',
         'Resolution date must be after alarm date!'),
    ]

    def action_acknowledge(self):
        self.write({'state': 'acknowledged'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_resolve(self, resolution=''):
        self.write({
            'state': 'resolved',
            'resolution': resolution or self.resolution,
            'resolved_date': fields.Datetime.now(),
        })

    def action_close(self):
        self.write({
            'state': 'closed',
            'closed_date': fields.Datetime.now(),
        })

    def action_create_service_order(self):
        self.ensure_one()
        return {
            'name': _('Service Order from Alarm'),
            'type': 'ir.actions.act_window',
            'res_model': 'utility.service.order',
            'view_mode': 'form',
            'context': {
                'default_customer_id': self.customer_id.id,
                'default_account_id': self.account_id.id,
                'default_meter_id': self.meter_id.id,
                'default_alarm_id': self.id,
                'default_description': f'Auto-generated from alarm: {self.description}',
            },
        }

    @api.model
    def cron_check_low_credit(self):
        """Cron job to check accounts with low/zero credit."""
        threshold_accounts = self.env['utility.account'].search([
            ('state', '=', 'active'),
            ('balance', '>', 0),
            ('balance', '<', 50),
        ])
        for account in threshold_accounts:
            existing = self.search([
                ('account_id', '=', account.id),
                ('alarm_type', '=', 'low_credit'),
                ('state', 'not in', ('resolved', 'closed')),
            ], limit=1)
            if not existing:
                self.create({
                    'alarm_type': 'low_credit',
                    'severity': 'warning' if account.balance > 10 else 'critical',
                    'customer_id': account.customer_id.id,
                    'account_id': account.id,
                    'meter_id': account.meter_id.id,
                    'description': f'Low credit: {account.balance:.2f} remaining on account {account.account_number}',
                })
        zero_accounts = self.env['utility.account'].search([
            ('state', '=', 'active'),
            ('balance', '<=', 0),
        ])
        for account in zero_accounts:
            existing = self.search([
                ('account_id', '=', account.id),
                ('alarm_type', '=', 'zero_credit'),
                ('state', 'not in', ('resolved', 'closed')),
            ], limit=1)
            if not existing:
                self.create({
                    'alarm_type': 'zero_credit',
                    'severity': 'critical',
                    'customer_id': account.customer_id.id,
                    'account_id': account.id,
                    'meter_id': account.meter_id.id,
                    'description': f'Zero credit on account {account.account_number}',
                })
        return True

    @api.model
    def create(self, vals):
        if vals.get('alarm_code', _('New')) == _('New'):
            vals['alarm_code'] = self.env['ir.sequence'].next_by_code('utility.alarm') or _('New')
        return super().create(vals)
