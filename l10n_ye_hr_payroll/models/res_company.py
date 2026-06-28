from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    social_insurance_min_base = fields.Float(
        string="Social Insurance Minimum Base (YER)", default=0.0,
        help="Floor for insurable salary. If 0, no minimum applies.")
    social_insurance_max_base = fields.Float(
        string="Social Insurance Maximum Base (YER)", default=0.0,
        help="Ceiling for insurable salary. If 0, no maximum applies.")
    social_insurance_employee_rate = fields.Float(
        string="Employee Insurance Rate (%)", default=6.0)
    social_insurance_employer_rate = fields.Float(
        string="Employer Insurance Rate (%)", default=9.0)
    tax_exemption_amount = fields.Float(
        string="Tax Exemption (YER/month)", default=10000.0,
        help="Statutory income tax exemption per month.")
    social_insurance_payable_account_id = fields.Many2one(
        'account.account', string="Social Insurance Payable Account",
        domain=[('deprecated', '=', False)],
        help="Liability account for social insurance withheld from employees.")
    social_insurance_expense_account_id = fields.Many2one(
        'account.account', string="Social Insurance Expense Account",
        domain=[('deprecated', '=', False)],
        help="Expense account for employer's social insurance contribution.")
    tax_payable_account_id = fields.Many2one(
        'account.account', string="Tax Payable Account",
        domain=[('deprecated', '=', False)],
        help="Liability account for income tax withheld from employees.")
    eos_provision_account_id = fields.Many2one(
        'account.account', string="EOS Provision Liability Account",
        domain=[('deprecated', '=', False)],
        help="Liability account for accrued End-of-Service provision.")
    eos_expense_account_id = fields.Many2one(
        'account.account', string="EOS Expense Account",
        domain=[('deprecated', '=', False)],
        help="Expense account for End-of-Service provision accrual.")

    def write(self, vals):
        res = super(ResCompany, self).write(vals)
        if 'tax_exemption_amount' in vals:
            for company in self:
                bracket = self.env['ye.tax.bracket'].search([
                    ('company_id', '=', company.id),
                    ('rate', '=', 0.0),
                    ('active', '=', True)
                ], order='from_amount asc', limit=1)
                if bracket and bracket.to_amount != vals['tax_exemption_amount']:
                    bracket.write({'to_amount': vals['tax_exemption_amount']})
        return res

