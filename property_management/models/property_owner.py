from odoo import api, fields, models, _


class PropertyOwner(models.Model):
    _name = 'property.owner'
    _description = 'Property Owner'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    active = fields.Boolean(default=True)
    partner_id = fields.Many2one('res.partner', string='Contact', required=True,
                                 domain=[('is_company', '=', False)])
    name = fields.Char(string='Name', related='partner_id.name', store=True, index=True)
    email = fields.Char(string='Email', related='partner_id.email')
    phone = fields.Char(string='Phone', related='partner_id.phone')
    mobile = fields.Char(string='Mobile', related='partner_id.mobile')
    image = fields.Binary(string='Image', related='partner_id.image_1920')

    owner_code = fields.Char(string='Owner Code', required=True, index=True)
    owner_type = fields.Selection([
        ('individual', 'Individual'),
        ('company', 'Company'),
        ('joint', 'Joint Ownership'),
        ('trust', 'Trust/Institution'),
    ], string='Owner Type', default='individual', required=True)

    property_ids = fields.One2many('property.property', 'owner_id', string='Properties')
    unit_ids = fields.One2many('property.unit', 'owner_id', string='Units')

    total_properties = fields.Integer(string='Total Properties', compute='_compute_counts', store=True)
    total_units = fields.Integer(string='Total Units', compute='_compute_counts', store=True)
    total_annual_income = fields.Monetary(string='Annual Income', compute='_compute_financials', store=True)
    total_maintenance_cost = fields.Monetary(string='Maintenance Cost', compute='_compute_financials', store=True)
    net_income = fields.Monetary(string='Net Income', compute='_compute_financials', store=True)

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    bank_account = fields.Char(string='Bank Account')
    tax_id = fields.Char(string='Tax ID/VAT')
    management_fee_percentage = fields.Float(string='Management Fee %', default=5.0, digits=(5, 2))
    last_settlement_date = fields.Date(string='Last Settlement Date')
    notes = fields.Text(string='Notes')

    def action_open_settlement_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Owner Settlement'),
            'res_model': 'property.owner.settlement.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_owner_id': self.id,
                'default_start_date': self.last_settlement_date or fields.Date.today().replace(day=1),
                'default_end_date': fields.Date.today(),
            },
        }

    _sql_constraints = [
        ('owner_code_unique', 'UNIQUE(owner_code, company_id)', 'Owner code must be unique per company!'),
    ]

    @api.depends('property_ids', 'unit_ids')
    def _compute_counts(self):
        for rec in self:
            rec.total_properties = len(rec.property_ids)
            rec.total_units = len(rec.unit_ids)

    @api.depends('property_ids')
    def _compute_financials(self):
        for rec in self:
            leases = self.env['property.lease'].search([
                ('unit_id.owner_id', '=', rec.id),
                ('state', '=', 'active'),
            ])
            rec.total_annual_income = sum(leases.mapped('annual_rent'))
            properties = rec.property_ids
            rec.total_maintenance_cost = sum(properties.mapped('total_maintenance_cost'))
            rec.net_income = rec.total_annual_income - rec.total_maintenance_cost

    def action_open_properties(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Properties'),
            'res_model': 'property.property',
            'view_mode': 'tree,form',
            'domain': [('owner_id', '=', self.id)],
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('owner_code'):
                vals['owner_code'] = self.env['ir.sequence'].next_by_code('property.owner') or '/'
        return super().create(vals_list)
