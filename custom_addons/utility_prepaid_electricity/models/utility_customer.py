from odoo import api, fields, models, _


class UtilityCustomerCategory(models.Model):
    _name = 'utility.customer.category'
    _description = 'Customer Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Category code must be unique!'),
    ]


class UtilityCustomer(models.Model):
    _name = 'utility.customer'
    _description = 'Utility Customer'
    _order = 'customer_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'customer_number'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    customer_number = fields.Char(string='Customer Number', required=True, index=True, copy=False,
                                  default=lambda self: _('New'))
    national_id = fields.Char(string='National ID / IQUAMA', index=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Contact', required=True,
                                 domain=[('company_type', 'in', ['person', 'company'])], tracking=True)
    account_number = fields.Char(string='Account Number', index=True, tracking=True)
    mobile = fields.Char(string='Mobile Phone', index=True)
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')

    address_street = fields.Char(string='Street')
    address_city = fields.Char(string='City')
    address_state = fields.Char(string='State/Province')
    address_zip = fields.Char(string='ZIP Code')
    country_id = fields.Many2one('res.country', string='Country')

    gps_latitude = fields.Float(string='GPS Latitude', digits=(10, 7))
    gps_longitude = fields.Float(string='GPS Longitude', digits=(10, 7))

    region_id = fields.Many2one('utility.region', string='Region', index=True, tracking=True)
    area_id = fields.Many2one('utility.area', string='Service Area', index=True, tracking=True)

    category_id = fields.Many2one('utility.customer.category', string='Customer Category', tracking=True)
    connection_status = fields.Selection([
        ('active', 'Active'),
        ('disconnected', 'Disconnected'),
        ('suspended', 'Suspended'),
        ('pending', 'Pending Connection'),
    ], string='Connection Status', default='active', index=True, tracking=True)
    customer_type = fields.Selection([
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
        ('government', 'Government'),
        ('agriculture', 'Agriculture'),
    ], string='Customer Type', default='residential', required=True, tracking=True)

    account_ids = fields.One2many('utility.account', 'customer_id', string='Utility Accounts')
    account_count = fields.Integer(string='Account Count', compute='_compute_account_count', store=True)
    meter_count = fields.Integer(string='Meter Count', compute='_compute_meter_count', store=True)

    active_account_id = fields.Many2one('utility.account', string='Primary Account',
                                        compute='_compute_active_account', store=True)

    document_ids = fields.One2many('ir.attachment', 'res_id', string='Documents',
                                   domain=[('res_model', '=', 'utility.customer')])

    _sql_constraints = [
        ('customer_number_uniq', 'UNIQUE(customer_number, company_id)', 'Customer number must be unique!'),
    ]

    @api.depends('account_ids')
    def _compute_account_count(self):
        for rec in self:
            rec.account_count = len(rec.account_ids)

    @api.depends('account_ids')
    def _compute_meter_count(self):
        for rec in self:
            rec.meter_count = len(rec.account_ids.mapped('meter_id').filtered(lambda m: m.active))

    @api.depends('account_ids', 'account_ids.state')
    def _compute_active_account(self):
        for rec in self:
            active = rec.account_ids.filtered(lambda a: a.state == 'active')[:1]
            rec.active_account_id = active.id if active else False

    def name_get(self):
        return [(rec.id, f'{rec.customer_number} - {rec.partner_id.name}') for rec in self]

    @api.model
    def create(self, vals):
        if vals.get('customer_number', _('New')) == _('New'):
            vals['customer_number'] = self.env['ir.sequence'].next_by_code('utility.customer') or _('New')
        return super().create(vals)
