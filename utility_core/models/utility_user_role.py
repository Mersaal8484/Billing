from odoo import fields, models


class UtilityUserRole(models.Model):
    _name = 'utility.user.role'
    _description = 'Utility User Role'
    _order = 'name'

    name = fields.Char('Role Name', required=True)
    code = fields.Char('Code', required=True)
    group_ids = fields.Many2many('res.groups', string='Groups')
    description = fields.Text('Description')
