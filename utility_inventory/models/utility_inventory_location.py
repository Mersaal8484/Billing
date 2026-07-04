from odoo import api, fields, models


class UtilityInventoryLocation(models.Model):
    _name = 'utility.inventory.location'
    _description = 'موقع المخزون'
    _rec_name = 'name'
    _parent_store = True
    _order = 'code, name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم الموقع', required=True, translate=True)
    code = fields.Char('كود الموقع', required=True)
    location_type = fields.Selection([
        ('warehouse', 'مستودع'),
        ('room', 'غرفة'),
        ('shelf', 'رف'),
    ], string='نوع الموقع', required=True, default='warehouse')
    parent_id = fields.Many2one('utility.inventory.location', 'الموقع الأب', index=True, ondelete='restrict')
    child_ids = fields.One2many('utility.inventory.location', 'parent_id', 'المواقع الفرعية')
    parent_path = fields.Char(index=True)

    _sql_constraints = [
        ('unique_code_company', 'unique(code, company_id)',
         'كود الموقع يجب أن يكون فريداً لكل شركة!'),
    ]
