from odoo import api, fields, models


class UtilityTeam(models.Model):
    _name = 'utility.team'
    _description = 'فريق عمل'
    _order = 'name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('Team Name', required=True)
    code = fields.Char('Team Code', required=True)
    team_leader_id = fields.Many2one('utility.staff', 'Team Leader')
    area_id = fields.Many2one('utility.region', 'Area', domain="[('type', '=', 'area')]")
    region_id = fields.Many2one('utility.region', 'Region', related='area_id.parent_id', store=True)
    staff_ids = fields.One2many('utility.staff', 'team_id', string='الأعضاء')
    member_count = fields.Integer('Member Count', compute='_compute_member_count', store=True)

    @api.depends('staff_ids')
    def _compute_member_count(self):
        for r in self:
            r.member_count = len(r.staff_ids)
