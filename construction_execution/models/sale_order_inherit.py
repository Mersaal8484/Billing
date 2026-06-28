from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    construction_project_id = fields.Many2one('construction.project',
        string='Construction Project', index=True)
    construction_boq_id = fields.Many2one('construction.boq',
        string='Source BOQ', index=True)
    construction_ipc_id = fields.Many2one('construction.ipc',
        string='Source IPC', index=True)
    is_construction_order = fields.Boolean(string='Construction Order',
        compute='_compute_is_construction', store=True)

    @api.depends('construction_project_id', 'construction_boq_id',
                 'construction_ipc_id')
    def _compute_is_construction(self):
        for rec in self:
            rec.is_construction_order = bool(
                rec.construction_project_id or
                rec.construction_boq_id or
                rec.construction_ipc_id
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

    def action_open_construction_boq(self):
        self.ensure_one()
        if not self.construction_boq_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bill of Quantities'),
            'res_model': 'construction.boq',
            'view_mode': 'form',
            'res_id': self.construction_boq_id.id,
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    construction_project_id = fields.Many2one('construction.project',
        related='order_id.construction_project_id', store=True, index=True)
    construction_boq_item_id = fields.Many2one('construction.boq.item',
        string='BOQ Item', index=True)
    construction_progress_line_id = fields.Many2one(
        'construction.progress.line', string='Progress Line', index=True)
    construction_ipc_line_id = fields.Many2one('construction.ipc.line',
        string='IPC Line', index=True)

    def action_open_boq_item(self):
        self.ensure_one()
        if not self.construction_boq_item_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOQ Item'),
            'res_model': 'construction.boq.item',
            'view_mode': 'form',
            'res_id': self.construction_boq_item_id.id,
        }
