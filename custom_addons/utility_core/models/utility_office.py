from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import re

PHONE_9_RE = re.compile(r'^\d{9}$')


class UtilityOffice(models.Model):
    _name = 'utility.office'
    _description = 'مكتب'
    _order = 'name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم المكتب', required=True)
    code = fields.Char('رمز المكتب', required=True)
    area_id = fields.Many2one('utility.region', 'المنطقة الفرعية', domain="[('type', '=', 'area')]")
    region_id = fields.Many2one('utility.region', 'المنطقة', related='area_id.parent_id', store=True)
    phone = fields.Char('الهاتف')
    address = fields.Text('العنوان')
    manager_id = fields.Many2one('res.users', 'المدير')

    _sql_constraints = [
        ('unique_office_code_company', 'unique(code, company_id)', 'رمز المكتب يجب أن يكون فريداً لكل شركة!'),
    ]

    @api.constrains('phone')
    def _check_phone_9_digits(self):
        for rec in self:
            if rec.phone and not PHONE_9_RE.match(rec.phone):
                raise ValidationError(
                    'رقم الهاتف يجب أن يتكون من 9 أرقام فقط، بدون مفتاح دولة (+967/00) أو شرطات.'
                )
