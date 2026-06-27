from datetime import date

from odoo import api, fields, models, _


class UtilityTariff(models.Model):
    _name = 'utility.tariff'
    _description = 'Utility Tariff'
    _inherit = ['mail.thread']
    _order = 'name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('Tariff Name', required=True)
    code = fields.Char('Tariff Code', required=True)
    category_id = fields.Many2one('utility.tariff.category', 'Category')
    tariff_type = fields.Selection([
        ('flat', 'Flat Rate'),
        ('block', 'Block/Tiered'),
        ('seasonal', 'Seasonal'),
        ('tou', 'Time of Use'),
        ('tier', 'Tiered'),
    ], string='Tariff Type', default='flat')
    price_per_kwh = fields.Float('Price per kWh')
    fixed_charge = fields.Float('Fixed Charge')
    service_charge = fields.Float('Service Charge')
    tax_percentage = fields.Float('Tax (%)')
    fuel_adjustment = fields.Float('Fuel Adjustment')
    effective_date = fields.Date('Effective Date')
    end_date = fields.Date('End Date')
    is_active = fields.Boolean('Active', compute='_compute_is_active', store=True)
    account_ids = fields.One2many('utility.customer', 'tariff_id', string='Accounts')
    block_ids = fields.One2many('utility.tariff.block', 'tariff_id', string='Rate Blocks',
                                copy=True)
    history_ids = fields.One2many('utility.tariff.history', 'tariff_id', string='History')
    minimum_charge = fields.Float('Minimum Charge')
    maximum_charge = fields.Float('Maximum Charge')

    _sql_constraints = [
        ('unique_tariff_code_company', 'unique(code, company_id)',
         'Tariff code must be unique per company!'),
    ]

    @api.depends('effective_date', 'end_date')
    def _compute_is_active(self):
        today = date.today()
        for r in self:
            if r.effective_date and r.effective_date > today:
                r.is_active = False
            elif r.end_date and r.end_date < today:
                r.is_active = False
            else:
                r.is_active = True

    def calculate_kwh(self, amount, date=None):
        self.ensure_one()
        date = date or fields.Date.today()
        unit_price = 0.0
        energy_charge = 0.0

        if self.tariff_type == 'flat':
            unit_price = self.price_per_kwh
            if unit_price:
                energy_charge = amount / unit_price
            kwh = energy_charge

        elif self.tariff_type in ('block', 'tier'):
            remaining = amount
            kwh = 0.0
            blocks = self.block_ids.sorted('sequence')
            for block in blocks:
                if remaining <= 0:
                    break
                block_kwh = block.to_kwh - block.from_kwh if block.to_kwh else remaining / block.price_per_kwh if block.price_per_kwh else 0
                if block.to_kwh:
                    block_cost = (block.to_kwh - block.from_kwh) * block.price_per_kwh
                    if remaining >= block_cost:
                        kwh += block.to_kwh - block.from_kwh
                        remaining -= block_cost
                    else:
                        kwh_in_block = remaining / block.price_per_kwh if block.price_per_kwh else 0
                        kwh += kwh_in_block
                        remaining = 0
                else:
                    kwh_in_block = remaining / block.price_per_kwh if block.price_per_kwh else 0
                    kwh += kwh_in_block
                    remaining = 0
                unit_price = block.price_per_kwh
            energy_charge = amount - remaining

        else:
            unit_price = self.price_per_kwh
            if unit_price:
                energy_charge = amount / unit_price
            kwh = energy_charge

        fixed = self.fixed_charge or 0.0
        service = self.service_charge or 0.0
        fuel = self.fuel_adjustment or 0.0
        tax = (energy_charge + fixed + service + fuel) * (self.tax_percentage / 100.0) if self.tax_percentage else 0.0
        total = energy_charge + fixed + service + fuel + tax

        return {
            'kwh': kwh,
            'unit_price': unit_price,
            'energy_charge': energy_charge,
            'fixed_charge': fixed,
            'service_charge': service,
            'fuel_adjustment': fuel,
            'tax': tax,
            'total': total,
        }

    def name_get(self):
        res = []
        for rec in self:
            name = f'[{rec.code}] {rec.name}'
            res.append((rec.id, name))
        return res


class UtilityTariffCategory(models.Model):
    _name = 'utility.tariff.category'
    _description = 'Utility Tariff Category'
    _order = 'sequence, name'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    sequence = fields.Integer('Sequence')
    description = fields.Text('Description')


class UtilityTariffBlock(models.Model):
    _name = 'utility.tariff.block'
    _description = 'Utility Tariff Block'
    _order = 'tariff_id, sequence'

    tariff_id = fields.Many2one('utility.tariff', 'Tariff', required=True, index=True, ondelete='cascade')
    sequence = fields.Integer('Sequence')
    name = fields.Char('Block Name')
    from_kwh = fields.Float('From (kWh)')
    to_kwh = fields.Float('To (kWh)')
    price_per_kwh = fields.Float('Price per kWh')
    from_month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'),
        ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='From Month')
    to_month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'),
        ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='To Month')
    time_from = fields.Float('Time From')
    time_to = fields.Float('Time To')


class UtilityTariffHistory(models.Model):
    _name = 'utility.tariff.history'
    _description = 'Utility Tariff History'
    _order = 'change_date desc, id desc'

    tariff_id = fields.Many2one('utility.tariff', 'Tariff', required=True, index=True, ondelete='cascade')
    account_id = fields.Many2one('utility.customer', 'Account')
    change_date = fields.Datetime('Change Date', default=fields.Datetime.now)
    old_price = fields.Float('Old Price')
    new_price = fields.Float('New Price')
    reason = fields.Char('Reason')
    changed_by = fields.Many2one('res.users', 'Changed By')

