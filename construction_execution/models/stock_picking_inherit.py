from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    construction_project_id = fields.Many2one('construction.project',
        string='Construction Project', index=True)
    construction_material_issue_id = fields.Many2one(
        'construction.material.issue', string='Material Issue', index=True)
    construction_material_return_id = fields.Many2one(
        'construction.material.return', string='Material Return', index=True)
    is_construction_picking = fields.Boolean(
        string='Construction Picking',
        compute='_compute_is_construction', store=True)

    @api.depends('construction_project_id',
                 'construction_material_issue_id',
                 'construction_material_return_id')
    def _compute_is_construction(self):
        for rec in self:
            rec.is_construction_picking = bool(
                rec.construction_project_id or
                rec.construction_material_issue_id or
                rec.construction_material_return_id
            )

    def action_open_construction_project(self):
        self.ensure_one()
        if not self.construction_project_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Construction Project'),
            'res_model': 'construction.project',
            'view_mode': 'form',
            'res_id': self.construction_project_id.id,
        }

    def action_open_material_issue(self):
        self.ensure_one()
        if not self.construction_material_issue_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Issue'),
            'res_model': 'construction.material.issue',
            'view_mode': 'form',
            'res_id': self.construction_material_issue_id.id,
        }

    def action_open_material_return(self):
        self.ensure_one()
        if not self.construction_material_return_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Return'),
            'res_model': 'construction.material.return',
            'view_mode': 'form',
            'res_id': self.construction_material_return_id.id,
        }


class StockMove(models.Model):
    _inherit = 'stock.move'

    construction_project_id = fields.Many2one('construction.project',
        related='picking_id.construction_project_id', store=True, index=True)
    construction_material_issue_line_id = fields.Many2one(
        'construction.material.issue.line',
        string='Material Issue Line', index=True)
    construction_material_return_line_id = fields.Many2one(
        'construction.material.return.line',
        string='Material Return Line', index=True)
    construction_boq_item_id = fields.Many2one('construction.boq.item',
        string='BOQ Item', index=True)
