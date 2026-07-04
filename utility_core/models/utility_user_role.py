from odoo import fields, models


class UtilityUserRole(models.Model):
    _name = 'utility.user.role'
    _description = 'صلاحية مستخدم'
    _order = 'name'

    name = fields.Char('Role Name', required=True)
    code = fields.Char('Code', required=True)
    group_ids = fields.Many2many('res.groups', string='المجموعات')
    description = fields.Text('Description')
