from odoo import api, fields, models, _


class UtilityVendingChannel(models.Model):
    _name = 'utility.vending.channel'
    _description = 'قناة بيع الكهرباء'
    _order = 'sequence, name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم القناة', required=True)
    code = fields.Char('رمز القناة', required=True, index=True)
    sequence = fields.Integer('التسلسل', default=10)
    channel_type = fields.Selection([
        ('pos', 'نقاط البيع'),
        ('portal', 'بوابة العميل'),
        ('api', 'API'),
        ('mobile_app', 'تطبيق الهاتف'),
        ('agent', 'وكيل بيع'),
        ('payment_gateway', 'بوابة دفع إلكترونية'),
        ('customer_service', 'خدمة العملاء'),
    ], 'نوع القناة', required=True, default='pos')

    description = fields.Text('الوصف')
    is_default = fields.Boolean('افتراضي', default=False,
        help='هل هذه القناة هي القناة الافتراضية؟')
    allow_self_service = fields.Boolean('تسمح بالخدمة الذاتية', default=False)
    require_approval = fields.Boolean('تتطلب موافقة', default=False)

    _sql_constraints = [
        ('code_unique', 'unique(code, company_id)', 'رمز القناة يجب أن يكون فريداً لكل شركة.'),
    ]
