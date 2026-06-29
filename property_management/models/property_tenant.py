from odoo import api, fields, models, _


class PropertyTenant(models.Model):
    _name = 'property.tenant'
    _description = 'Property Tenant'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    active = fields.Boolean(default=True)
    partner_id = fields.Many2one('res.partner', string='Contact', required=True)
    name = fields.Char(string='Name', related='partner_id.name', store=True, index=True)
    email = fields.Char(string='Email', related='partner_id.email')
    phone = fields.Char(string='Phone', related='partner_id.phone')
    mobile = fields.Char(string='Mobile', related='partner_id.mobile')
    image = fields.Binary(string='Image', related='partner_id.image_1920')

    tenant_code = fields.Char(string='Tenant Code', required=True, index=True)
    tenant_type = fields.Selection([
        ('individual', 'Individual'),
        ('company', 'Company'),
        ('family', 'Family'),
    ], string='Tenant Type', default='individual', required=True)

    lease_ids = fields.One2many('property.lease', 'tenant_id', string='Lease History')
    active_lease_id = fields.Many2one('property.lease', string='Active Lease',
                                      compute='_compute_active_lease', store=True)
    current_unit_id = fields.Many2one('property.unit', string='Current Unit',
                                      compute='_compute_active_lease', store=True)

    total_leases = fields.Integer(string='Total Leases', compute='_compute_counts', store=True)
    total_paid = fields.Monetary(string='Total Paid', compute='_compute_financials', store=True)
    outstanding_balance = fields.Monetary(string='Outstanding Balance', compute='_compute_financials', store=True)
    outstanding_maintenance = fields.Integer(string='Open Maintenance',
                                             compute='_compute_maintenance_count', store=True)

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    id_document = fields.Binary(string='ID Document', attachment=True)
    emergency_contact = fields.Char(string='Emergency Contact')
    emergency_phone = fields.Char(string='Emergency Phone')
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('tenant_code_unique', 'UNIQUE(tenant_code, company_id)', 'Tenant code must be unique per company!'),
    ]

    @api.depends('lease_ids', 'lease_ids.state')
    def _compute_active_lease(self):
        for rec in self:
            active_lease = rec.lease_ids.filtered(lambda l: l.state == 'active')[:1]
            rec.active_lease_id = active_lease
            rec.current_unit_id = active_lease.unit_id if active_lease else False

    @api.depends('lease_ids')
    def _compute_counts(self):
        for rec in self:
            rec.total_leases = len(rec.lease_ids)

    @api.depends('lease_ids')
    def _compute_financials(self):
        for rec in self:
            payments = self.env['property.payment'].search([
                ('tenant_id', '=', rec.id),
                ('state', '=', 'paid'),
            ])
            rec.total_paid = sum(payments.mapped('amount'))
            # Calculate only overdue/delayed payments (date <= today), excluding future scheduled payments
            pending = self.env['property.payment.schedule'].search([
                ('tenant_id', '=', rec.id),
                ('state', 'in', ('pending', 'overdue')),
                ('date', '<=', fields.Date.today()),
            ])
            rec.outstanding_balance = sum(pending.mapped('amount'))

    @api.depends('lease_ids')
    def _compute_maintenance_count(self):
        for rec in self:
            rec.outstanding_maintenance = len(self.env['property.maintenance'].search([
                ('tenant_id', '=', rec.id),
                ('state', '!=', 'done'),
            ]))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('tenant_code'):
                vals['tenant_code'] = self.env['ir.sequence'].next_by_code('property.tenant') or '/'
        return super().create(vals_list)
