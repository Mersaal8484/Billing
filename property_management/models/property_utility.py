from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PropertyUtility(models.Model):
    _name = 'property.utility'
    _description = 'Utility Meter'
    _order = 'unit_id, utility_type'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='unit_id.company_id', store=True)
    property_id = fields.Many2one('property.property', string='Property',
                                  related='unit_id.property_id', store=True)
    unit_id = fields.Many2one('property.unit', string='Unit', required=True, index=True)

    utility_type = fields.Many2one('property.utility.type', string='Utility Type',
                                   required=True)
    meter_number = fields.Char(string='Meter Number', required=True, index=True)
    provider = fields.Char(string='Provider/Company')
    account_number = fields.Char(string='Account Number')

    initial_reading = fields.Float(string='Initial Reading', default=0.0, digits=(12, 3))
    last_reading = fields.Float(string='Last Reading', digits=(12, 3))
    last_reading_date = fields.Date(string='Last Reading Date')
    total_consumption = fields.Float(string='Total Consumption',
                                     compute='_compute_consumption', store=True,
                                     digits=(12, 3))

    reading_ids = fields.One2many('property.meter.reading', 'meter_id',
                                  string='Reading History')
    unit_rate = fields.Monetary(string='Unit Rate', default=0.0,
                                help='Rate per unit of consumption')
    pricing_method = fields.Selection([('fixed', 'Fixed Rate'), ('tiered', 'Tiered Pricing')], string='Pricing Method', default='fixed')
    tier_ids = fields.One2many('property.utility.tier', 'meter_id', string='Pricing Tiers')
    estimated_monthly = fields.Monetary(string='Estimated Monthly Cost', default=0.0)

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('meter_unique', 'UNIQUE(meter_number, unit_id)',
         'Meter number must be unique per unit!'),
    ]

    @api.depends('initial_reading', 'last_reading')
    def _compute_consumption(self):
        for rec in self:
            rec.total_consumption = rec.last_reading - rec.initial_reading

    def action_record_reading(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Record Reading'),
            'res_model': 'property.meter.reading',
            'view_mode': 'form',
            'context': {
                'default_meter_id': self.id,
                'default_unit_id': self.unit_id.id,
                'default_reading': self.last_reading,
                'default_date': fields.Date.today(),
            },
            'target': 'new',
        }


class PropertyUtilityType(models.Model):
    _name = 'property.utility.type'
    _description = 'Utility Type'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)


class PropertyMeterReading(models.Model):
    _name = 'property.meter.reading'
    _description = 'Meter Reading'
    _order = 'date desc'

    meter_id = fields.Many2one('property.utility', string='Meter', required=True, index=True)
    unit_id = fields.Many2one('property.unit', string='Unit', related='meter_id.unit_id', store=True)
    property_id = fields.Many2one('property.property', related='unit_id.property_id', store=True)

    date = fields.Date(string='Reading Date', required=True, default=fields.Date.today)
    reading = fields.Float(string='Reading', required=True, digits=(12, 3))
    consumption = fields.Float(string='Consumption', compute='_compute_consumption',
                               store=True, digits=(12, 3))
    unit_rate = fields.Monetary(string='Unit Rate',
                                related='meter_id.unit_rate')
    cost = fields.Monetary(string='Cost', compute='_compute_cost', store=True)
    estimated = fields.Boolean(string='Estimated Reading', default=False)
    image = fields.Binary(string='Meter Photo', attachment=True)
    notes = fields.Text(string='Notes')
    currency_id = fields.Many2one('res.currency', related='meter_id.currency_id')
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True)

    @api.depends('reading', 'meter_id.last_reading')
    def _compute_consumption(self):
        for rec in self:
            prev = rec.meter_id.last_reading or rec.meter_id.initial_reading or 0.0
            rec.consumption = rec.reading - prev

    @api.depends('consumption', 'meter_id.unit_rate', 'meter_id.pricing_method', 'meter_id.tier_ids')
    def _compute_cost(self):
        for rec in self:
            if rec.meter_id.pricing_method == 'tiered' and rec.meter_id.tier_ids:
                total_cost = 0.0
                remaining = rec.consumption
                for tier in rec.meter_id.tier_ids.sorted('min_consumption'):
                    if remaining <= 0:
                        break
                    tier_range = tier.max_consumption - tier.min_consumption
                    if remaining > tier_range:
                        total_cost += tier_range * tier.rate
                        remaining -= tier_range
                    else:
                        total_cost += remaining * tier.rate
                        remaining = 0
                rec.cost = total_cost
            else:
                rec.cost = rec.consumption * (rec.meter_id.unit_rate or 0.0)

    def action_generate_utility_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Utility Invoice'),
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.invoice_id.id,
            }
        tenant = self.unit_id.current_tenant_id
        if not tenant or not tenant.partner_id:
            raise UserError(_("No active tenant found for this unit to generate a utility invoice."))

        property_rec = self.property_id
        income_account = property_rec._get_service_income_account() if property_rec else self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', self.unit_id.company_id.id),
        ], limit=1)
        journal = property_rec._get_journal_for_method('other') if property_rec else self.env['account.journal'].search([
            ('company_id', '=', self.unit_id.company_id.id),
            ('type', '=', 'sale'),
        ], limit=1)

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': tenant.partner_id.id,
            'invoice_date': self.date,
            'currency_id': self.currency_id.id,
            'journal_id': journal.id if journal else False,
            'invoice_line_ids': [(0, 0, {
                'name': f'Utility Bill - {self.meter_id.utility_type.name} (Reading: {self.reading})',
                'quantity': 1.0,
                'price_unit': self.cost,
                'account_id': income_account.id,
                'analytic_distribution': {str(self.unit_id.analytic_account_id.id): 100.0} if self.unit_id and self.unit_id.analytic_account_id else False,
            })],
        })
        self.invoice_id = invoice.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Utility Invoice'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        }


    def write(self, vals):
        res = super().write(vals)
        if 'reading' in vals:
            for rec in self:
                rec.meter_id.write({
                    'last_reading': rec.reading,
                    'last_reading_date': rec.date,
                })
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.meter_id.write({
                'last_reading': rec.reading,
                'last_reading_date': rec.date,
            })
        return records


class PropertyServiceCharge(models.Model):
    _name = 'property.service.charge'
    _description = 'Service Charge'
    _order = 'date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='property_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    property_id = fields.Many2one('property.property', string='Property', required=True, index=True)
    unit_id = fields.Many2one('property.unit', string='Unit', index=True)
    tenant_id = fields.Many2one('property.tenant', string='Tenant', index=True)

    name = fields.Char(string='Description', required=True, translate=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.today, index=True)
    service_type = fields.Selection([
        ('maintenance', 'Maintenance'),
        ('security', 'Security'),
        ('cleaning', 'Cleaning'),
        ('gardening', 'Gardening'),
        ('parking', 'Parking'),
        ('amenity', 'Amenity Fee'),
        ('management', 'Management Fee'),
        ('other', 'Other'),
    ], string='Service Type', required=True, default='maintenance')

    amount = fields.Monetary(string='Amount', required=True)
    is_recurring = fields.Boolean(string='Recurring Charge', default=False)
    frequency = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
    ], string='Frequency', default='monthly')

    invoice_id = fields.Many2one('account.move', string='Invoice')
    paid = fields.Boolean(string='Paid', default=False)
    notes = fields.Text(string='Notes')


class PropertyUtilityTier(models.Model):
    _name = 'property.utility.tier'
    _description = 'Utility Pricing Tier'
    _order = 'min_consumption'

    meter_id = fields.Many2one('property.utility', string='Meter', required=True, ondelete='cascade')
    min_consumption = fields.Float(string='Min Consumption', required=True)
    max_consumption = fields.Float(string='Max Consumption', required=True)
    rate = fields.Monetary(string='Rate per Unit', required=True)
    currency_id = fields.Many2one('res.currency', related='meter_id.currency_id')
