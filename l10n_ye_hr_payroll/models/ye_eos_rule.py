from odoo import api, fields, models


class YeEosRule(models.Model):
    _name = 'ye.eos.rule'
    _description = 'Yemeni End-of-Service Provision Rule'

    name = fields.Char(required=True)
    months_per_year = fields.Float(
        string="Months per Service Year", default=1.0,
        help="How many months of salary per year of service. "
             "Accrued monthly as: (wage x months_per_year / 12).")
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
