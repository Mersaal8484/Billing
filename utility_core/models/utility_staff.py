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
    user_role_id = fields.Many2one('utility.user.role', string='Role / الدور')
    phone = fields.Char('Phone')
    mobile = fields.Char('Mobile')

    def write(self, vals):
        res = super(UtilityStaff, self).write(vals)
        if 'user_role_id' in vals or 'user_id' in vals:
            for record in self:
                if record.user_id and record.user_role_id:
                    # Clear previous custom groups from utility ERP to assign the new ones cleanly
                    utility_category = self.env.ref('utility_core.module_category_utility_erp', raise_if_not_found=False)
                    if utility_category:
                        utility_groups = self.env['res.groups'].search([('category_id', '=', utility_category.id)])
                        record.user_id.write({'groups_id': [(3, group.id) for group in utility_groups]})
                    
                    # Assign new groups
                    if record.user_role_id.group_ids:
                        record.user_id.write({'groups_id': [(4, group.id) for group in record.user_role_id.group_ids]})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super(UtilityStaff, self).create(vals_list)
        for record in records:
            if record.user_id and record.user_role_id and record.user_role_id.group_ids:
                record.user_id.write({'groups_id': [(4, group.id) for group in record.user_role_id.group_ids]})
        return records
