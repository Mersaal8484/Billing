from odoo import fields, models


class UtilityUserRole(models.Model):
    _name = 'utility.user.role'
    _description = 'صلاحية مستخدم'
    _order = 'name'

    name = fields.Char('الاسم', required=True)
    code = fields.Char('الرمز', required=True)
    group_ids = fields.Many2many('res.groups', string='المجموعات')
    description = fields.Text('الوصف')
