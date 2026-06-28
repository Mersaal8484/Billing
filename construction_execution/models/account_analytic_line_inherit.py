from odoo import api, fields, models, _


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    construction_project_id = fields.Many2one('construction.project',
        string='Construction Project', index=True)
    construction_project_code = fields.Char(string='Project Code',
        related='construction_project_id.code', store=True)
    construction_boq_item_id = fields.Many2one('construction.boq.item',
        string='BOQ Item', index=True)
    construction_progress_line_id = fields.Many2one(
        'construction.progress.line', string='Progress Line', index=True)
    construction_variation_line_id = fields.Many2one(
        'construction.variation.line', string='Variation Line', index=True)
    construction_issue_line_id = fields.Many2one(
        'construction.material.issue.line',
        string='Material Issue Line', index=True)
    cost_type = fields.Selection([
        ('material', 'Material'),
        ('labor', 'Labor'),
        ('equipment', 'Equipment'),
        ('subcontract', 'Subcontract'),
        ('overhead', 'Overhead'),
        ('other', 'Other'),
    ], string='Cost Type', index=True)
