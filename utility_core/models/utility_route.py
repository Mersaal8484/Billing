from odoo import api, fields, models


class UtilityRoute(models.Model):
    _name = 'utility.route'
    _description = 'Utility Route'
    _order = 'name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('Route Name', required=True)
    code = fields.Char('Route Code', required=True)
    area_id = fields.Many2one('utility.region', 'Area', domain="[('type', '=', 'area')]")
    zone_id = fields.Many2one('utility.region', 'Zone', domain="[('type', '=', 'zone')]")
    region_id = fields.Many2one('utility.region', 'Region', related='area_id.parent_id', store=True)
    customer_ids = fields.One2many('utility.customer', 'route_id', string='عقود المشتركين')
    inspector_id = fields.Many2one('utility.staff', string='الكشاف', domain="[('role', '=', 'inspector')]")
    cashier_id = fields.Many2one('utility.staff', string='المحصل', domain="[('role', '=', 'cashier')]")
    supervisor_id = fields.Many2one('utility.staff', string='المشرف', domain="[('role', '=', 'supervisor')]")

    _sql_constraints = [
        ('unique_route_code_area', 'unique(code, area_id)', 'Route code must be unique per area!'),
    ]
