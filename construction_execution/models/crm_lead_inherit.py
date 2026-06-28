from odoo import api, fields, models, _


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    construction_project_id = fields.Many2one('construction.project',
        string='Construction Project', index=True, readonly=True)
    is_converted_to_construction = fields.Boolean(
        string='Converted to Construction', readonly=True)

    def action_create_construction_project(self):
        self.ensure_one()
        if self.construction_project_id:
            raise UserError(_('A construction project already exists for '
                              'this lead!'))
        if self.stage_id and not self.stage_id.is_won:
            raise UserError(_('The lead must be in a Won stage before '
                              'creating a construction project!'))
        project = self.env['construction.project'].create({
            'name': self.name or self.partner_name or 'New Project',
            'partner_id': self.partner_id.id if self.partner_id else False,
            'user_id': self.user_id.id or self.env.user.id,
            'description': self.description,
            'contract_amount': self.expected_revenue or 0.0,
            'project_stage': 'planning',
        })
        self.write({
            'construction_project_id': project.id,
            'is_converted_to_construction': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Construction Project'),
            'res_model': 'construction.project',
            'view_mode': 'form',
            'res_id': project.id,
        }

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
