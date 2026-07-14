from odoo import api, fields, models, _


class UtilityReversalReason(models.Model):
    _name = 'utility.reversal.reason'
    _description = 'سبب العكس'
    _order = 'sequence, name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('السبب', required=True)
    code = fields.Char('الرمز', required=True, index=True)
    sequence = fields.Integer('التسلسل', default=10)

    requires_approval = fields.Boolean('يتطلب موافقة', default=True)
    description = fields.Text('الوصف')
    category = fields.Selection([
        ('technical', 'فني'),
        ('customer', 'عميل'),
        ('system', 'نظام'),
        ('billing', 'فوترة'),
        ('other', 'أخرى'),
    ], 'الفئة', default='other')

    _sql_constraints = [
        ('reason_code_unique', 'unique(code, company_id)', 'رمز السبب يجب أن يكون فريداً لكل شركة.'),
    ]
