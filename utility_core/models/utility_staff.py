from odoo import api, fields, models


class UtilityStaff(models.Model):
    _name = 'utility.staff'
    _description = 'Utility Staff'
    _order = 'name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', 'User')
    employee_code = fields.Char('Employee Code')
    name = fields.Char('Name', required=True)
    team_id = fields.Many2one('utility.team', 'Team')
    role = fields.Selection([
        ('manager', 'Manager'),
        ('supervisor', 'Supervisor'),
        ('technician', 'Technician'),
        ('cashier', 'Cashier'),
        ('inspector', 'Inspector'),
        ('engineer', 'Engineer'),
    ], string='Role', default='technician')
    phone = fields.Char('Phone')
    mobile = fields.Char('Mobile')
