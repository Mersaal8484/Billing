from odoo import api, fields, models, _


class UtilitySubscriberCategory(models.Model):
    _name = 'utility.subscriber.category'
    _description = 'Subscriber Category'
    _parent_store = True
    _parent_name = 'parent_id'
    _order = 'sequence, code'

    name = fields.Char('الاسم', required=True, translate=True)
    code = fields.Char('الكود', required=True)
    sequence = fields.Integer('الترتيب', default=10)
    
    # هرمية الفئات
    parent_id = fields.Many2one('utility.subscriber.category', 'الفئة الرئيسية',
        index=True, ondelete='cascade')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('utility.subscriber.category', 'parent_id', 'الفئات الفرعية')
    level = fields.Selection([
        ('category', 'فئة رئيسية'),
        ('subcategory', 'فئة فرعية'),
    ], compute='_compute_level', store=True, string='المستوى')
    
    # الخصم المدعوم
    subsidized_enabled = fields.Boolean('تفعيل الخصم المدعوم', default=False,
        help='تفعيل الخصم المدعوم لأول N كيلوواط/ساعة لهذه الفئة')
    subsidized_max_units = fields.Float('الحد الأقصى للوحدات المدعومة', default=100.0,
        help='أول X kWh مدعومة (مثلاً 100)')
    subsidized_percentage = fields.Float('نسبة الدعم (%)', default=100.0,
        help='نسبة الدعم: 100% = مجاناً، 50% = نصف السعر')
    subsidized_price_per_kwh = fields.Float('سعر الوحدة المدعومة', 
        help='سعر ثابت للوحدات المدعومة (يترك فارغاً لحساب النسبة)')
    
    # إعدادات الحسابات المحاسبية
    subsidy_account_id = fields.Many2one('account.account', 'حساب مصروف الدعم',
        help='حساب مصروف دعم الاستهلاك (مدين)')
    revenue_account_id = fields.Many2one('account.account', 'حساب الإيراد')
    
    # إعدادات الفوترة
    default_tariff_id = fields.Many2one('utility.tariff', 'التعرفة الافتراضية')
    default_contract_template_id = fields.Many2one('utility.contract.template', 'قالب العقد الافتراضي')
    
    description = fields.Text('الوصف')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)

    _sql_constraints = [
        ('code_unique_per_company', 'unique(code, company_id)',
         'كود الفئة يجب أن يكون فريداً لكل شركة!'),
    ]

    @api.depends('parent_id')
    def _compute_level(self):
        for rec in self:
            rec.level = 'subcategory' if rec.parent_id else 'category'

    @api.depends('parent_id.name', 'name', 'code')
    def _compute_display_name(self):
        for rec in self:
            name = f"[{rec.code}] {rec.name}"
            if rec.parent_id:
                name = f"{rec.parent_id.name} / {name}"
            rec.display_name = name

    def _get_subsidized_amount(self, consumption, tariff):
        """حساب مبلغ الخصم المدعوم حسب الفئة والاستهلاك"""
        self.ensure_one()
        if not self.subsidized_enabled or consumption <= 0:
            return (0.0, 0.0, '')
        
        subsidized_units = min(consumption, self.subsidized_max_units)
        
        if self.subsidized_price_per_kwh:
            unit_price = -abs(self.subsidized_price_per_kwh)
        elif tariff and tariff.price_per_kwh:
            discount_price = tariff.price_per_kwh * (self.subsidized_percentage / 100.0)
            unit_price = -abs(discount_price)
        else:
            unit_price = -130.0
        
        return (subsidized_units, unit_price, f'خصم استهلاك مدعوم - {subsidized_units} وحدة')
