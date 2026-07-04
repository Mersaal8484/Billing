from odoo import api, fields, models, _


class UtilityInstallation(models.Model):
    _name = 'utility.installation'
    _description = 'تركيبة'
    _order = 'installation_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('Installation Number', required=True, index=True, default=lambda self: _('New'))
    service_order_id = fields.Many2one('utility.service.order', 'Service Order')
    customer_id = fields.Many2one('utility.customer', 'Customer', required=True)
    account_id = fields.Many2one('utility.customer', 'Account', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'Meter', required=True)
    meter_serial = fields.Char('Meter Serial')
    meter_type_id = fields.Many2one('utility.meter.type', 'Meter Type')
    installation_date = fields.Datetime('Installation Date', default=fields.Datetime.now)
    installer_id = fields.Many2one('res.users', 'Installer')
    address = fields.Text('Address')
    seal_number = fields.Char('Seal Number')
    photo_ids = fields.One2many('ir.attachment', 'res_id', string='الصور',
                                domain=[('res_model', '=', 'utility.installation')])
    notes = fields.Text('Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('installed', 'Installed'),
        ('verified', 'Verified'),
        ('failed', 'Failed'),
    ], string='الحالة', default='draft')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.installation') or _('New')
        return super().create(vals_list)
