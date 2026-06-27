from odoo import api, fields, models, _


class UtilityContractTemplate(models.Model):
    _name = 'utility.contract.template'
    _description = 'Utility Contract Template'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    
    # تكوين التكرار والفوترة
    recurring_rule_type = fields.Selection([
        ('monthly', 'شهري'),
        ('bi_monthly', 'نصف شهري'),
        ('quarterly', 'ربع سنوي'),
        ('yearly', 'سنوي'),
    ], default='monthly', required=True)
    recurring_invoicing_type = fields.Selection([
        ('postpaid', 'آجل (Post-paid)'),
        ('prepaid', 'مسبق (Pre-paid)'),
    ], default='postpaid', required=True)
    recurring_interval = fields.Integer(default=1, string='الفاصل الزمني للدورة')

    # البنود
    line_ids = fields.One2many('utility.contract.template.line', 'template_id', copy=True, string='بنود العقد')

    # إعدادات الحسابات والتعرفة
    pricelist_id = fields.Many2one('product.pricelist')
    journal_id = fields.Many2one('account.journal', domain="[('type', 'in', ['sale', 'general'])]")
    tariff_id = fields.Many2one('utility.tariff')
    
    # سير العمل الآلي
    sale_autoconfirm = fields.Boolean(default=True, string='تأكيد أمر البيع تلقائياً')
    create_invoice_automatically = fields.Boolean(default=True, string='إنشاء الفاتورة تلقائياً')
    validate_invoice_automatically = fields.Boolean(default=False)

    # الدفع التلقائي
    is_auto_pay = fields.Boolean(string='دفع تلقائي')
    auto_pay_retries = fields.Integer(default=3)
    auto_pay_retry_hours = fields.Integer(default=1)

    active = fields.Boolean(default=True)


class UtilityContractTemplateLine(models.Model):
    _name = 'utility.contract.template.line'
    _description = 'Contract Template Line'

    template_id = fields.Many2one('utility.contract.template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    
    product_id = fields.Many2one('product.product', required=True)
    name = fields.Text(string='Description', translate=True)
    
    quantity = fields.Float(default=1.0)
    uom_id = fields.Many2one('uom.uom')
    
    price_type = fields.Selection([
        ('fixed', 'سعر ثابت'),
        ('from_product', 'من المنتج'),
        ('formula', 'معادلة'),
        ('meter_reading', 'حسب قراءة العداد'),
    ], default='fixed', required=True)
    
    specific_price = fields.Float(string='السعر')
    formula_code = fields.Text(string='كود المعادلة', help='Python expression using variables: reading, consumption, tariff')
    
    # تصنيف البند للفوترة
    meter_line_type = fields.Selection([
        ('consumption', 'الاستهلاك'),
        ('fixed_fee', 'رسم ثابت'),
        ('service_charge', 'رسم خدمة'),
        ('discount', 'خصم'),
        ('tax', 'ضريبة'),
    ], string='نوع بند العداد')

    # الربط مع معادلات محرك الاحتساب
    qty_formula_id = fields.Many2one('utility.formula', 'معادلة الكمية',
        help='معادلة ديناميكية تحسب الكمية تلقائياً (متغيرات: consumption, tariff, account, category)')
    is_subsidized = fields.Boolean('خصم مدعوم',
        help='يطبق الخصم حسب فئة المشترك')

