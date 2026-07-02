from odoo import api, fields, models, _


class UtilityServiceOrder(models.Model):
    _name = 'utility.service.order'
    _description = 'Utility Service Order'
    _rec_name = 'order_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_requested desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    order_number = fields.Char('Order Number', required=True, index=True, default=lambda self: _('New'))
    date_requested = fields.Datetime('Date Requested', default=fields.Datetime.now)
    date_scheduled = fields.Datetime('Date Scheduled')
    date_completed = fields.Datetime('Date Completed')
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
    ], string='Service Type', required=True)
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='normal')
    customer_id = fields.Many2one('utility.customer', 'Customer', index=True)
    account_id = fields.Many2one('utility.customer', 'Account', related='customer_id', store=True, index=True)
    meter_id = fields.Many2one('utility.meter', 'Meter', index=True)
    region_id = fields.Many2one('utility.region', 'Region', related='customer_id.region_id', store=True)
    area_id = fields.Many2one('utility.region', 'Area', related='customer_id.area_id', store=True)
    zone_id = fields.Many2one('utility.region', 'Zone', domain="[('type', '=', 'zone')]")

    old_meter_id = fields.Many2one('utility.meter', 'Old Meter')
    new_meter_id = fields.Many2one('utility.meter', 'New Meter')
    description = fields.Text('Description', required=True)
    technician_id = fields.Many2one('res.users', 'Technician')
    team_id = fields.Many2one('utility.team', 'Team')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft')
    findings = fields.Text('Findings')
    meter_reading_before = fields.Float('Meter Reading Before')
    meter_reading_after = fields.Float('Meter Reading After')
    seal_number_old = fields.Char('Old Seal Number')
    seal_number_new = fields.Char('New Seal Number')
    tamper_evidence = fields.Boolean('Tamper Evidence')
    tamper_notes = fields.Text('Tamper Notes')
    cost_estimate = fields.Monetary('Cost Estimate', currency_field='company_currency_id')
    actual_cost = fields.Monetary('Actual Cost', currency_field='company_currency_id')
    notes = fields.Text('Notes')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Currency')

    _sql_constraints = [
        ('unique_order_number_company', 'unique(order_number, company_id)',
         'Order number must be unique per company!'),
    ]

    def action_approve(self):
        self.state = 'approved'

    def action_schedule(self):
        self.state = 'scheduled'

    def action_start(self):
        self.state = 'in_progress'

    def action_complete(self):
        if self.service_type == 'meter_replacement' and self.new_meter_id:
            self.new_meter_id.write({
                'account_id': self.account_id.id,
                'customer_id': self.customer_id.id,
            })
            if self.old_meter_id:
                self.old_meter_id.write({
                    'account_id': False,
                    'customer_id': False,
                })
        self.state = 'completed'
        self.date_completed = fields.Datetime.now()

    def action_cancel(self):
        self.state = 'cancelled'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('order_number', _('New')) == _('New'):
                vals['order_number'] = self.env['ir.sequence'].next_by_code('utility.service.order') or _('New')
        return super().create(vals_list)
