from odoo import api, fields, models


class UtilityOffice(models.Model):
    _name = 'utility.office'
    _description = 'Utility Office'
    _order = 'name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('Office Name', required=True)
    code = fields.Char('Office Code', required=True)
    area_id = fields.Many2one('utility.region', 'Area', domain="[('type', '=', 'area')]")
    region_id = fields.Many2one('utility.region', 'Region', related='area_id.parent_id', store=True)
    phone = fields.Char('Phone')
    address = fields.Text('Address')
    manager_id = fields.Many2one('res.users', 'Manager')

    _sql_constraints = [
        ('unique_office_code_company', 'unique(code, company_id)', 'Office code must be unique per company!'),
    ]
