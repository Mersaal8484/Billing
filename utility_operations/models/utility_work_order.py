from odoo import api, fields, models, _


class UtilityWorkOrder(models.Model):
    _name = 'utility.work.order'
    _description = 'أمر عمل'
    _rec_name = 'work_order_number'
    _order = 'date_created desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    work_order_number = fields.Char('Work Order Number', required=True, index=True, default=lambda self: _('New'))
    service_order_id = fields.Many2one('utility.service.order', 'Service Order')
    customer_id = fields.Many2one('utility.customer', 'Customer')
    account_id = fields.Many2one('utility.customer', 'Account', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'Meter')
    work_type = fields.Selection([
        ('installation', 'Installation'),
        ('maintenance', 'Maintenance'),
        ('repair', 'Repair'),
        ('inspection', 'Inspection'),
        ('disconnection', 'Disconnection'),
        ('reconnection', 'Reconnection'),
        ('meter_reading', 'Meter Reading'),
        ('site_visit', 'Site Visit'),
        ('other', 'Other'),
    ], string='نوع العمل', required=True)
    description = fields.Text('Description', required=True)
    assigned_technician_id = fields.Many2one('res.users', 'Assigned Technician')
    team_id = fields.Many2one('utility.team', 'Team')
    date_created = fields.Datetime('Date Created', default=fields.Datetime.now)
    date_scheduled = fields.Datetime('Date Scheduled')
    date_started = fields.Datetime('Date Started')
    date_completed = fields.Datetime('Date Completed')
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='الأولوية', default='normal')
    gps_check_in = fields.Char('GPS Check-In')
    gps_check_out = fields.Char('GPS Check-Out')
    customer_signature = fields.Binary('Customer Signature')
    before_photos = fields.One2many('ir.attachment', 'res_id', string='الصور قبل',
                                    domain=[('res_model', '=', 'utility.work.order')])
    after_photos = fields.One2many('ir.attachment', 'res_id', string='الصور بعد',
                                   domain=[('res_model', '=', 'utility.work.order')])
    parts_used = fields.Text('Parts Used')
    labor_hours = fields.Float('Labor Hours')
    cost_estimate = fields.Monetary('Cost Estimate', currency_field='company_currency_id')
    actual_cost = fields.Monetary('Actual Cost', currency_field='company_currency_id')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='العملة')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('verified', 'Verified'),
        ('cancelled', 'Cancelled'),
    ], string='الحالة', default='draft')
    notes = fields.Text('Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('work_order_number', _('New')) == _('New'):
                vals['work_order_number'] = self.env['ir.sequence'].next_by_code('utility.work.order') or _('New')
        return super().create(vals_list)
