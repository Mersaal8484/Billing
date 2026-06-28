from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    social_insurance_min_base = fields.Float(
        related='company_id.social_insurance_min_base', readonly=False)
    social_insurance_max_base = fields.Float(
        related='company_id.social_insurance_max_base', readonly=False)
    social_insurance_employee_rate = fields.Float(
        related='company_id.social_insurance_employee_rate', readonly=False)
    social_insurance_employer_rate = fields.Float(
        related='company_id.social_insurance_employer_rate', readonly=False)
    tax_exemption_amount = fields.Float(
        related='company_id.tax_exemption_amount', readonly=False)
    social_insurance_payable_account_id = fields.Many2one(
        related='company_id.social_insurance_payable_account_id', readonly=False)
    social_insurance_expense_account_id = fields.Many2one(
        related='company_id.social_insurance_expense_account_id', readonly=False)
    tax_payable_account_id = fields.Many2one(
        related='company_id.tax_payable_account_id', readonly=False)
    eos_provision_account_id = fields.Many2one(
        related='company_id.eos_provision_account_id', readonly=False)
    eos_expense_account_id = fields.Many2one(
        related='company_id.eos_expense_account_id', readonly=False)
