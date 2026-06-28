from odoo import api, fields, models, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    construction_project_id = fields.Many2one('construction.project',
        string='Construction Project', index=True)
    construction_material_request_id = fields.Many2one(
        'construction.material.request', string='Material Request', index=True)
    is_construction_order = fields.Boolean(string='Construction Order',
        compute='_compute_is_construction', store=True)

    @api.depends('construction_project_id',
                 'construction_material_request_id')
    def _compute_is_construction(self):
        for rec in self:
            rec.is_construction_order = bool(
                rec.construction_project_id or
                rec.construction_material_request_id
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

    def action_open_material_request(self):
        self.ensure_one()
        if not self.construction_material_request_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Request'),
            'res_model': 'construction.material.request',
            'view_mode': 'form',
            'res_id': self.construction_material_request_id.id,
        }

    def button_confirm(self):
        result = super().button_confirm()
        for rec in self:
            if rec.construction_material_request_id:
                rec.construction_material_request_id.write(
                    {'state': 'ordered'})
        return result


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    construction_project_id = fields.Many2one('construction.project',
        related='order_id.construction_project_id', store=True, index=True)
    construction_material_request_line_id = fields.Many2one(
        'construction.material.request.line',
        string='Material Request Line', index=True)
    construction_boq_item_id = fields.Many2one('construction.boq.item',
        string='BOQ Item', index=True)
    construction_cost_entry_id = fields.Many2one('construction.cost.entry',
        string='Cost Entry', index=True)

    def action_open_material_request_line(self):
        self.ensure_one()
        if not self.construction_material_request_line_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Request Line'),
            'res_model': 'construction.material.request.line',
            'view_mode': 'form',
            'res_id': self.construction_material_request_line_id.id,
        }
