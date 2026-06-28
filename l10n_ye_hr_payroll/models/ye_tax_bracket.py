from odoo import api, fields, models


class YeTaxBracket(models.Model):
    _name = 'ye.tax.bracket'
    _description = 'Yemeni Income Tax Bracket'
    _order = 'from_amount'

    name = fields.Char(required=True)
    from_amount = fields.Float(string="From (YER)", required=True)
    to_amount = fields.Float(
        string="To (YER)",
        help="Leave empty for the final bracket (unlimited).")
    rate = fields.Float(string="Rate (%)", required=True)
    fixed_amount = fields.Float(
        string="Cumulative Fixed Amount (YER)", default=0.0,
        help="Total tax from all previous brackets.")
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    @api.model
    def compute_tax(self, base_amount, company_id=None):
        """
        Computes progressive income tax for a given base amount (Gross - Employee Social Insurance)
        using the active tax brackets for the company.
        """
        if company_id is None:
            company_id = self.env.company.id
        brackets = self.search([
            ('company_id', '=', company_id),
            ('active', '=', True)
        ], order='from_amount asc')

        if not brackets:
            return 0.0

        tax = 0.0
        for bracket in brackets:
            start = bracket.from_amount - 1 if bracket.from_amount > 0 else 0.0
            end = bracket.to_amount if bracket.to_amount > 0.0 else float('inf')

            if base_amount > start:
                taxable_in_bracket = min(base_amount, end) - start
                tax += taxable_in_bracket * (bracket.rate / 100.0)
        return tax

    @api.model_create_multi
    def create(self, vals_list):
        records = super(YeTaxBracket, self).create(vals_list)
        for record in records:
            if record.rate == 0.0 and record.active:
                if record.company_id.tax_exemption_amount != record.to_amount:
                    record.company_id.write({'tax_exemption_amount': record.to_amount})
        return records

    def write(self, vals):
        res = super(YeTaxBracket, self).write(vals)
        if any(f in vals for f in ['to_amount', 'active', 'rate', 'company_id']):
            for record in self:
                if record.rate == 0.0 and record.active:
                    if record.company_id.tax_exemption_amount != record.to_amount:
                        record.company_id.write({'tax_exemption_amount': record.to_amount})
        return res

