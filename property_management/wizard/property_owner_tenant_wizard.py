from odoo import api, fields, models, _


class PropertyOwnerTenantWizard(models.TransientModel):
    _name = 'property.owner.tenant.wizard'
    _description = 'Wizard to Create Owner/Tenant and Partner Together'

    creation_type = fields.Selection([
        ('owner', 'Property Owner'),
        ('tenant', 'Tenant'),
    ], string='Creation Type', default='owner', required=True)

    name = fields.Char(string='Name / Company Name', required=True)
    is_company = fields.Boolean(string='Is a Company', default=True)
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
    tax_id = fields.Char(string='Tax ID / VAT')

    street = fields.Char(string='Street')
    city = fields.Char(string='City')
    country_id = fields.Many2one('res.country', string='Country')

    owner_code = fields.Char(string='Owner Code')
    tenant_code = fields.Char(string='Tenant Code')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    def action_create(self):
        self.ensure_one()
        partner_vals = {
            'name': self.name,
            'is_company': self.is_company,
            'email': self.email,
            'phone': self.phone,
            'mobile': self.mobile,
            'vat': self.tax_id,
            'street': self.street,
            'city': self.city,
            'country_id': self.country_id.id,
            'company_id': self.company_id.id,
        }
        partner = self.env['res.partner'].create(partner_vals)

        if self.creation_type == 'owner':
            owner_vals = {
                'partner_id': partner.id,
                'owner_code': self.owner_code or '/',
                'owner_type': 'company' if self.is_company else 'individual',
                'tax_id': self.tax_id,
                'company_id': self.company_id.id,
            }
            owner = self.env['property.owner'].create(owner_vals)
            return {
                'name': _('Property Owner'),
                'view_mode': 'form',
                'res_model': 'property.owner',
                'res_id': owner.id,
                'type': 'ir.actions.act_window',
            }
        else:
            tenant_vals = {
                'partner_id': partner.id,
                'tenant_code': self.tenant_code or '/',
                'tenant_type': 'company' if self.is_company else 'individual',
                'company_id': self.company_id.id,
            }
            tenant = self.env['property.tenant'].create(tenant_vals)
            return {
                'name': _('Tenant'),
                'view_mode': 'form',
                'res_model': 'property.tenant',
                'res_id': tenant.id,
                'type': 'ir.actions.act_window',
            }
