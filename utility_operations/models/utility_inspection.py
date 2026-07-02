from odoo import api, fields, models, _


class UtilityInspection(models.Model):
    _name = 'utility.inspection'
    _description = 'Utility Inspection'
    _order = 'inspection_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('Inspection Number', required=True, index=True, default=lambda self: _('New'))
    service_order_id = fields.Many2one('utility.service.order', 'Service Order')
    customer_id = fields.Many2one('utility.customer', 'Customer')
    account_id = fields.Many2one('utility.customer', 'Account', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'Meter')
    inspection_type = fields.Selection([
        ('pre_installation', 'Pre-Installation'),
        ('post_installation', 'Post-Installation'),
        ('routine', 'Routine'),
        ('tamper', 'Tamper'),
        ('safety', 'Safety'),
        ('theft', 'Theft'),
    ], string='Inspection Type', required=True)
    inspector_id = fields.Many2one('res.users', 'Inspector')
    inspection_date = fields.Datetime('Inspection Date', default=fields.Datetime.now)
    findings = fields.Text('Findings')
    condition_rating = fields.Integer('Condition Rating (1-5)')
    photos = fields.One2many('ir.attachment', 'res_id', string='Photos',
                             domain=[('res_model', '=', 'utility.inspection')])
    address = fields.Text('Address')
    customer_signature = fields.Binary('Customer Signature')
    inspector_signature = fields.Binary('Inspector Signature')
    is_passed = fields.Boolean('Passed')
    notes = fields.Text('Notes')
    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='scheduled')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.inspection') or _('New')
        return super().create(vals_list)
