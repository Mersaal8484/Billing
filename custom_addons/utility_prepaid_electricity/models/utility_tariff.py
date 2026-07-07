from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class UtilityTariffCategory(models.Model):
    _name = 'utility.tariff.category'
    _description = 'Tariff Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Tariff category code must be unique!'),
    ]


class UtilityTariff(models.Model):
    _name = 'utility.tariff'
    _description = 'Electricity Tariff'
    _order = 'code, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    name = fields.Char(string='Tariff Name', required=True, translate=True, tracking=True)
    code = fields.Char(string='Tariff Code', required=True, index=True, tracking=True)
    category_id = fields.Many2one('utility.tariff.category', string='Category', required=True, tracking=True)

    tariff_type = fields.Selection([
        ('flat', 'Flat Rate'),
        ('block', 'Block Tariff'),
        ('seasonal', 'Seasonal Tariff'),
        ('tou', 'Time of Use'),
        ('tier', 'Tier Pricing'),
    ], string='Tariff Type', default='flat', required=True, tracking=True)

    price_per_kwh = fields.Monetary(string='Price per kWh', digits=(16, 6), default=0.0,
                                    help='Base price per kWh for flat rate tariffs')
    fixed_charge = fields.Monetary(string='Fixed Charge', default=0.0,
                                   help='Fixed monthly/service charge')
    service_charge = fields.Monetary(string='Service Charge', default=0.0)
    tax_percentage = fields.Float(string='Tax %', digits=(5, 4), default=0.0,
                                  help='VAT or sales tax as decimal (e.g. 0.15 for 15%%)')
    fuel_adjustment = fields.Monetary(string='Fuel Adjustment', digits=(16, 6), default=0.0,
                                      help='Per-kWh fuel cost adjustment')

    account_ids = fields.One2many('utility.account', 'tariff_id', string='Accounts')
    account_count = fields.Integer(string='Account Count', compute='_compute_account_count', store=True)
    sale_count = fields.Integer(string='Sale Count', compute='_compute_sale_count', store=True)

    block_ids = fields.One2many('utility.tariff.block', 'tariff_id', string='Pricing Blocks',
                                copy=True)
    history_ids = fields.One2many('utility.tariff.history', 'tariff_id', string='Change History')

    effective_date = fields.Date(string='Effective Date', default=fields.Date.today)
    end_date = fields.Date(string='End Date')
    is_active = fields.Boolean(string='Currently Active', compute='_compute_is_active', store=True, index=True)

    minimum_charge = fields.Monetary(string='Minimum Monthly Charge', default=0.0)
    maximum_charge = fields.Monetary(string='Maximum Monthly Charge', default=0.0)

    _sql_constraints = [
        ('code_company_uniq', 'UNIQUE(code, company_id)', 'Tariff code must be unique per company!'),
    ]

    @api.depends('account_ids')
    def _compute_account_count(self):
        for rec in self:
            rec.account_count = len(rec.account_ids)

    @api.depends('account_ids.sale_ids')
    def _compute_sale_count(self):
        for rec in self:
            rec.sale_count = len(rec.account_ids.mapped('sale_ids'))

    @api.depends('effective_date', 'end_date')
    def _compute_is_active(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_active = bool(
                rec.effective_date and rec.effective_date <= today and
                (not rec.end_date or rec.end_date >= today)
            )

    def name_get(self):
        return [(rec.id, f'[{rec.code}] {rec.name}') for rec in self]

    def calculate_kwh(self, amount, date=None):
        """
        Calculate the kWh for a given purchase amount using this tariff.
        Returns dict with kwh, charges breakdown, and total.
        """
        self.ensure_one()
        if self.tariff_type == 'flat':
            return self._calculate_flat(amount)
        elif self.tariff_type == 'block':
            return self._calculate_block(amount)
        elif self.tariff_type == 'seasonal':
            return self._calculate_seasonal(amount, date)
        elif self.tariff_type == 'tou':
            return self._calculate_tou(amount, date)
        elif self.tariff_type == 'tier':
            return self._calculate_tier(amount)
        return self._calculate_flat(amount)

    def _calculate_flat(self, amount):
        effective_price = self.price_per_kwh + self.fuel_adjustment
        if effective_price <= 0:
            raise ValidationError(_('Tariff price must be greater than zero.'))
        kwh = amount / effective_price
        fixed = self.fixed_charge
        service = self.service_charge
        subtotal = kwh * effective_price
        tax = subtotal * self.tax_percentage
        total = subtotal + fixed + service + tax
        charge_data = {
            'kwh': kwh,
            'unit_price': effective_price,
            'energy_charge': subtotal,
            'fixed_charge': fixed,
            'service_charge': service,
            'fuel_adjustment': self.fuel_adjustment * kwh,
            'tax': tax,
            'total': total,
        }
        return charge_data

    def _calculate_block(self, amount):
        blocks = self.block_ids.sorted('sequence')
        if not blocks:
            return self._calculate_flat(amount)
        remaining = amount
        total_kwh = 0.0
        total_energy = 0.0
        total_fuel = 0.0
        for block in blocks:
            if remaining <= 0:
                break
            block_kwh = remaining / (block.price_per_kwh + self.fuel_adjustment)
            if block.to_kwh and block_kwh > (block.to_kwh - block.from_kwh + 1):
                block_kwh = block.to_kwh - block.from_kwh + 1
                block_cost = block_kwh * (block.price_per_kwh + self.fuel_adjustment)
                remaining -= block_cost
            else:
                block_cost = block_kwh * (block.price_per_kwh + self.fuel_adjustment)
                remaining -= block_cost
            total_kwh += block_kwh
            total_energy += block_kwh * block.price_per_kwh
            total_fuel += block_kwh * self.fuel_adjustment
        fixed = self.fixed_charge
        service = self.service_charge
        tax = (total_energy + total_fuel) * self.tax_percentage
        total = total_energy + total_fuel + fixed + service + tax
        return {
            'kwh': total_kwh,
            'unit_price': total_energy / total_kwh if total_kwh else 0.0,
            'energy_charge': total_energy,
            'fixed_charge': fixed,
            'service_charge': service,
            'fuel_adjustment': total_fuel,
            'tax': tax,
            'total': total,
        }

    def _calculate_seasonal(self, amount, date=None):
        date = date or fields.Date.today()
        month = date.month
        season_blocks = self.block_ids.filtered(
            lambda b: b.from_month and b.to_month and
            b.from_month <= month <= b.to_month
        )
        if season_blocks:
            return self._calculate_flat(amount)
        return self._calculate_flat(amount)

    def _calculate_tou(self, amount, date=None):
        return self._calculate_flat(amount)

    def _calculate_tier(self, amount):
        return self._calculate_block(amount)
