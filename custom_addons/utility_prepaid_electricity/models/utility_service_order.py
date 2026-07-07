from odoo import api, fields, models, _


class UtilityServiceOrder(models.Model):
    _name = 'utility.service.order'
    _description = 'Service Order'
    _order = 'date_requested desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'order_number'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)

    order_number = fields.Char(string='Order Number', required=True, index=True, copy=False,
                               default=lambda self: _('New'))
    date_requested = fields.Datetime(string='Date Requested', default=fields.Datetime.now, required=True, index=True)
    date_scheduled = fields.Date(string='Scheduled Date')
    date_completed = fields.Datetime(string='Completed Date')

    service_type = fields.Selection([
        ('new_connection', 'New Connection'),
        ('meter_replacement', 'Meter Replacement'),
        ('meter_removal', 'Meter Removal'),
        ('meter_test', 'Meter Test'),
        ('inspection', 'Inspection'),
        ('disconnection', 'Disconnection'),
        ('reconnection', 'Reconnection'),
        ('tamper_investigation', 'Tamper Investigation'),
        ('site_survey', 'Site Survey'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    ], string='Service Type', required=True, index=True, tracking=True)

    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='normal', index=True, required=True)

    customer_id = fields.Many2one('utility.customer', string='Customer', index=True, tracking=True)
    account_id = fields.Many2one('utility.account', string='Account', index=True, tracking=True)
    meter_id = fields.Many2one('utility.meter', string='Meter', index=True, tracking=True)
    region_id = fields.Many2one('utility.region', related='customer_id.region_id', store=True, index=True)
    area_id = fields.Many2one('utility.area', related='customer_id.area_id', store=True, index=True)

    alarm_id = fields.Many2one('utility.alarm', string='Related Alarm', index=True)

    old_meter_id = fields.Many2one('utility.meter', string='Old Meter',
                                   help='For meter replacement/removal')
    new_meter_id = fields.Many2one('utility.meter', string='New Meter',
                                   help='For meter replacement/new connection')

    description = fields.Text(string='Description', required=True)
    technician_id = fields.Many2one('res.users', string='Assigned Technician', tracking=True)
    team_members = fields.Text(string='Team Members')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', index=True, tracking=True, required=True)

    findings = fields.Text(string='Findings / Report')
    meter_reading_before = fields.Float(string='Meter Reading Before', digits=(16, 2))
    meter_reading_after = fields.Float(string='Meter Reading After', digits=(16, 2))
    seal_number_old = fields.Char(string='Old Seal Number')
    seal_number_new = fields.Char(string='New Seal Number')
    tamper_evidence = fields.Boolean(string='Tamper Evidence Found')
    tamper_notes = fields.Text(string='Tamper Notes')

    cost_estimate = fields.Monetary(string='Cost Estimate')
    actual_cost = fields.Monetary(string='Actual Cost')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    invoice_id = fields.Many2one('account.move', string='Related Invoice')

    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('order_number_uniq', 'UNIQUE(order_number, company_id)', 'Order number must be unique!'),
    ]

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_schedule(self):
        self.write({'state': 'scheduled'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_complete(self):
        self.ensure_one()
        now = fields.Datetime.now()
        self.write({
            'state': 'completed',
            'date_completed': now,
        })
        # Update meter if replacement
        if self.new_meter_id and self.old_meter_id:
            self.old_meter_id.write({
                'status_id': self.env.ref('utility_prepaid_electricity.meter_status_decommissioned').id,
            })
            if self.account_id:
                self.account_id.write({'meter_id': self.new_meter_id.id})
                self.new_meter_id.write({'account_id': self.account_id.id})
        self.env['utility.audit'].create({
            'model': 'utility.service.order',
            'res_id': self.id,
            'action': 'complete',
            'description': f'Service order {self.order_number} completed: {self.service_type}',
            'user_id': self.env.user.id,
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    @api.model
    def create(self, vals):
        if vals.get('order_number', _('New')) == _('New'):
            vals['order_number'] = self.env['ir.sequence'].next_by_code('utility.service.order') or _('New')
        return super().create(vals)
