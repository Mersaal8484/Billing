from odoo import api, fields, models


class HrContract(models.Model):
    _inherit = 'hr.contract'

    housing_allowance = fields.Float(string="Housing Allowance", default=0.0)
    transport_allowance = fields.Float(string="Transport Allowance", default=0.0)
    other_allowance = fields.Float(string="Other Variable Allowance", default=0.0)
    social_insurance_number = fields.Char(string="Social Insurance No.")
    eos_rule_id = fields.Many2one(
        'ye.eos.rule', string="EOS Provision Rule",
        ondelete='restrict',
        help="End-of-Service provision rule. If empty, defaults to 1 month/year.")
