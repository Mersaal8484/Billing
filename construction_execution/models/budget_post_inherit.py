from odoo import fields, models


class AccountBudgetPost(models.Model):
    _inherit = 'account.budget.post'

    construction_budget_line_ids = fields.One2many(
        'construction.budget.line', 'budget_post_id',
        string='Construction Budget Lines')
