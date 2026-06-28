from odoo import api, fields, models, _


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_project_id = fields.Many2one('construction.project',
        string='Construction Project', index=True)
    boq_item_count = fields.Integer(string='BOQ Items',
        compute='_compute_boq_item_count')
    total_boq_amount = fields.Monetary(string='Total BOQ Amount',
        compute='_compute_boq_item_count')

    @api.depends('construction_project_id')
    def _compute_boq_item_count(self):
        for rec in self:
            if rec.construction_project_id:
                items = rec.construction_project_id.boq_ids.item_ids
                rec.boq_item_count = len(items)
                rec.total_boq_amount = sum(items.mapped('amount'))
            else:
                rec.boq_item_count = 0
                rec.total_boq_amount = 0.0

    def action_open_construction_project(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Construction Project'),
            'res_model': 'construction.project',
            'view_mode': 'form',
            'res_id': self.construction_project_id.id,
        }


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_project_id = fields.Many2one('construction.project',
        related='project_id.construction_project_id', store=True, index=True)
    boq_item_id = fields.Many2one('construction.boq.item',
        string='BOQ Item', index=True)
    boq_code = fields.Char(string='BOQ Code',
        related='boq_item_id.code', store=True)
    boq_amount = fields.Monetary(string='BOQ Amount',
        related='boq_item_id.amount', store=True)
    currency_id = fields.Many2one('res.currency',
        related='company_id.currency_id')

    def action_open_boq_item(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOQ Item'),
            'res_model': 'construction.boq.item',
            'view_mode': 'form',
            'res_id': self.boq_item_id.id,
        }
