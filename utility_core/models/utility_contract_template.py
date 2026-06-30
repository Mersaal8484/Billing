from datetime import date

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
    subscriber_ids = fields.Many2many('utility.subscriber', string='أنواع المشتركين')

    # إعدادات الحسابات والتعرفة
    pricelist_id = fields.Many2one('product.pricelist')
    journal_id = fields.Many2one('account.journal', domain="[('type', 'in', ['sale', 'general'])]")

    # ── تسعير (دمج utility.tariff) ──────────────────────────────────────
    pricing_mode = fields.Selection([
        ('flat', 'سعر موحّد'),
        ('block', 'شرائح تدريجية'),
        ('tier', 'مستوى واحد'),
        ('seasonal', 'موسمي'),
        ('tou', 'حسب وقت الاستخدام'),
    ], string='نمط التسعير', default='flat')
    price_per_kwh = fields.Float('سعر الكيلوواط/ساعة', default=0.0)
    fixed_charge = fields.Float('رسم خدمة ثابت', default=0.0,
        help='مبلغ شهري ثابت لا يتأثر بالاستهلاك')
    service_charge = fields.Float('رسم خدمة إضافية', default=0.0)
    min_charge = fields.Float('الحد الأدنى للفوترة', default=0.0)
    max_charge = fields.Float('الحد الأقصى للفوترة', default=0.0)
    effective_date = fields.Date('تاريخ السريان')
    end_date = fields.Date('تاريخ الانتهاء')
    is_active = fields.Boolean('فعّال', compute='_compute_is_active', store=True)

    # رسوم محلية (معلم/نظافة/مجلس محلي) — تُحسب على أساس الاستهلاك
    local_fee_per_kwh = fields.Float('رسم محلي لكل kWh (افتراضي)', default=0.0,
        help='السعر الموحد للرسوم المحلية عند استخدام meter_line_type=local_fee')
    local_fee_mu_allim = fields.Float('رسم المعلم لكل kWh', default=0.0)
    local_fee_cleaning = fields.Float('رسم النظافة لكل kWh', default=0.0)

    # خصم الدعم — أول N وحدة تُخصم على الجهة الداعمة
    discount_first_units = fields.Float('وحدات الدعم الأولى', default=0.0,
        help='عدد الوحدات (kWh) المدعومة في الفاتورة')
    discount_unit_value = fields.Float('قيمة الخصم للوحدة', default=0.0,
        help='قيمة الخصم المحتسبة لكل وحدة مدعومة')

    # الشرائح التدريجية — تظهر فقط حين pricing_mode in (block,tier,seasonal,tou)
    block_ids = fields.One2many('utility.contract.template.block', 'template_id',
        string='الشرائح التدريجية', copy=True)
    history_ids = fields.One2many('utility.contract.template.history', 'template_id',
        string='سجل التغييرات', readonly=True)

    # سير العمل الآلي
    sale_autoconfirm = fields.Boolean(default=True, string='تأكيد أمر البيع تلقائياً')
    create_invoice_automatically = fields.Boolean(default=True, string='إنشاء الفاتورة تلقائياً')
    validate_invoice_automatically = fields.Boolean(default=False)

    # الدفع التلقائي
    is_auto_pay = fields.Boolean(string='دفع تلقائي')
    auto_pay_retries = fields.Integer(default=3)
    auto_pay_retry_hours = fields.Integer(default=1)

    active = fields.Boolean(default=True)

    @api.depends('effective_date', 'end_date')
    def _compute_is_active(self):
        today = date.today()
        for r in self:
            if r.effective_date and r.effective_date > today:
                r.is_active = False
            elif r.end_date and r.end_date < today:
                r.is_active = False
            else:
                r.is_active = True

    def action_sync_lines_with_template(self):
        self.ensure_one()
        # البحث عن المنتجات الافتراضية
        Product = self.env['product.product']
        kwh_product = self.env.ref('utility_core.utility_product_kwh', raise_if_not_found=False) or Product.search([('type', '=', 'service')], limit=1)
        fixed_product = self.env.ref('utility_core.utility_product_fixed_fee', raise_if_not_found=False) or Product.search([('type', '=', 'service')], limit=1)
        service_product = self.env.ref('utility_core.utility_product_service_charge', raise_if_not_found=False) or Product.search([('type', '=', 'service')], limit=1)

        existing_types = self.line_ids.mapped('meter_line_type')

        # مزامنة أو إنشاء بند الاستهلاك
        if 'consumption' not in existing_types and self.price_per_kwh > 0:
            self.env['utility.contract.template.line'].create({
                'template_id': self.id,
                'sequence': 10,
                'product_id': kwh_product.id if kwh_product else False,
                'name': f'استهلاك كهرباء ({self.name})',
                'price_type': 'meter_reading',
                'meter_line_type': 'consumption',
                'specific_price': self.price_per_kwh,
            })

        # مزامنة أو إنشاء بند الرسم الثابت
        if 'fixed_fee' not in existing_types and self.fixed_charge > 0:
            self.env['utility.contract.template.line'].create({
                'template_id': self.id,
                'sequence': 20,
                'product_id': fixed_product.id if fixed_product else False,
                'name': f'رسوم اشتراك وصيانة العداد ({self.name})',
                'price_type': 'fixed',
                'meter_line_type': 'fixed_fee',
                'specific_price': self.fixed_charge,
            })

        # مزامنة أو إنشاء بند رسوم الخدمة
        if 'service_charge' not in existing_types and self.service_charge > 0:
            self.env['utility.contract.template.line'].create({
                'template_id': self.id,
                'sequence': 25,
                'product_id': service_product.id if service_product else False,
                'name': f'رسوم خدمات إضافية ({self.name})',
                'price_type': 'fixed',
                'meter_line_type': 'service_charge',
                'specific_price': self.service_charge,
            })

        # تحديث الأسعار للبنود الحالية لتتطابق تماماً مع بيانات القالب
        for line in self.line_ids:
            if line.meter_line_type == 'consumption':
                line.specific_price = self.price_per_kwh
            elif line.meter_line_type == 'fixed_fee':
                line.specific_price = self.fixed_charge
            elif line.meter_line_type == 'service_charge':
                line.specific_price = self.service_charge

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('مزامنة ناجحة'),
                'message': _('تم التناغم ومزامنة بنود القالب مع التعرفة المحددة بنجاح تام!'),
                'sticky': False,
                'type': 'success',
            }
        }


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
        ('meter_reading', 'حسب قراءة العداد'),
    ], default='fixed', required=True)

    specific_price = fields.Float(string='السعر')

    # تصنيف البند للفوترة
    meter_line_type = fields.Selection([
        ('consumption', 'الاستهلاك'),
        ('fixed_fee', 'رسم ثابت'),
        ('service_charge', 'رسم خدمة'),
        ('local_fee', 'رسم محلي'),
        ('discount', 'خصم'),
    ], string='نوع بند العداد')

    local_fee_kind = fields.Selection([
        ('municipality', 'مجلس محلي'),
        ('mu_allim', 'المعلم'),
        ('cleaning', 'نظافة'),
        ('other', 'أخرى'),
    ], string='نوع الرسم المحلي')

    # الربط مع معادلات محرك الاحتساب
    qty_formula_id = fields.Many2one('utility.formula', 'معادلة الكمية',
        help='معادلة ديناميكية تحسب الكمية تلقائياً (متغيرات: consumption, template, account, category)')
    is_subsidized = fields.Boolean('خصم مدعوم',
        help='يطبق الخصم حسب فئة المشترك — يعمل فقط مع meter_line_type=discount')

