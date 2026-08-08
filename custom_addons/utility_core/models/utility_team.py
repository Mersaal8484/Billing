from odoo import api, fields, models


class UtilityTeam(models.Model):
    _name = 'utility.team'
    _description = 'فريق عمل'
    _order = 'name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم الفريق', required=True)
    code = fields.Char('رمز الفريق', required=True)
    team_leader_id = fields.Many2one('utility.staff', 'قائد الفريق')
    area_id = fields.Many2one('utility.region', 'المنطقة الفرعية', domain="[('type', '=', 'area')]")
    region_id = fields.Many2one('utility.region', 'المنطقة', related='area_id.parent_id', store=True)
    staff_ids = fields.One2many('utility.staff', 'team_id', string='الأعضاء')
    member_count = fields.Integer('عدد الأعضاء', compute='_compute_member_count', store=True)

    @api.depends('staff_ids')
    def _compute_member_count(self):
        for r in self:
            r.member_count = len(r.staff_ids)
