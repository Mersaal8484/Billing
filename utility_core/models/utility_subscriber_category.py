from odoo import api, fields, models, _


class UtilitySubscriberCategory(models.Model):
    _name = 'utility.subscriber.category'
    _description = 'فئة المشترك'
    _order = 'sequence, code'

    name = fields.Char('الاسم', required=True, translate=True)
    code = fields.Char('الكود', required=True)
    sequence = fields.Integer('الترتيب', default=10)
    description = fields.Text('الوصف')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)

    _sql_constraints = [
        ('code_unique_per_company', 'unique(code, company_id)',
         'كود الفئة يجب أن يكون فريداً لكل شركة!'),
    ]

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}"
