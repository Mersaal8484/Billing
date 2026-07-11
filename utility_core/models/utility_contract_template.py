from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityContractTemplate(models.Model):
    _name = 'utility.contract.template'
    _description = 'قالب عقد الكهرباء'

    name = fields.Char('الاسم', required=True, translate=True)
    code = fields.Char('الرمز', required=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )

    # تكوين التكرار والفوترة
    recurring_rule_type = fields.Selection([
        ('monthly', 'شهري'),
        ('bi_monthly', 'نصف شهري'),
        ('quarterly', 'ربع سنوي'),
        ('yearly', 'سنوي'),
    ], default='monthly', required=True)
    recurring_invoicing_type = fields.Selection([
        ('postpaid', 'آجل'),
        ('prepaid', 'مسبق'),
    ], default='postpaid', required=True)
    recurring_interval = fields.Integer(default=1, string='الفاصل الزمني للدورة')

    # البنود
    line_ids = fields.One2many('utility.contract.template.line', 'template_id', copy=True, string='بنود العقد')
    subscriber_category_ids = fields.Many2many('utility.subscriber.category', string='فئات المشتركين الرئيسية', required=True)
    subscriber_ids = fields.Many2many('utility.subscriber', string='انواع المشتركين', required=True)
    scope = fields.Selection([
        ('global', 'عام على جميع المناطق'),
        ('restricted', 'مخصص لمناطق محددة')
    ], string='نطاق التغطية الجغرافية', default='global', required=True)
    region_ids = fields.Many2many(
        'utility.region',
        'utility_contract_template_region_rel',
        'template_id',
        'region_id',
        string='المناطق الرئيسية المسموح بها',
        domain="[('type', '=', 'region')]",
        help="المناطق الرئيسية المسموح بها لهذا القالب"
    )
    area_ids = fields.Many2many(
        'utility.region',
        'utility_contract_template_area_rel',
        'template_id',
        'region_id',
        string='المناطق الفرعية المسموح بها',
        domain="[('type', '=', 'area')]",
        help="المناطق الفرعية/الفروع المسموح بها لهذا القالب"
    )

    # إعدادات الحسابات والتعرفة
    pricelist_id = fields.Many2one('product.pricelist', 'قائمة الأسعار')
    journal_id = fields.Many2one('account.journal', 'اليومية', domain="[('type', 'in', ['sale', 'general'])]")

    # ── تسعير (دمج utility.tariff) ──────────────────────────────────────
    pricing_mode = fields.Selection([
        ('flat', 'سعر موحّد بدون شرائح'),
        ('tier', 'Flat Tier / سعر شريحة واحدة'),
        ('block', 'Progressive Tier / شرائح تصاعدية'),
        ('seasonal', 'موسمي'),
        ('tou', 'حسب وقت الاستخدام'),
    ], string='نمط التسعير', default='flat',
        help=(
            'سعر موحّد: سعر ثابت لكل الاستهلاك بدون شرائح. '
            'Flat Tier: اختيار شريحة واحدة حسب إجمالي الاستهلاك وتطبيق سعرها على كامل الاستهلاك. '
            'Progressive Tier: تقسيم الاستهلاك على الشرائح وتطبيق سعر كل شريحة على الجزء الواقع داخلها.'
        ))
    price_per_kwh = fields.Monetary('سعر الكيلوواط/ساعة', default=0.0, currency_field='currency_id')
    service_charge = fields.Monetary('رسم الخدمة الثابت', default=0.0, currency_field='currency_id',
        help='مبلغ شهري ثابت لا يتأثر بالاستهلاك (رسوم الاشتراك والصيانة)')
    fixed_charge = fields.Monetary(
        string='رسم ثابت (مرادف)',
        related='service_charge',
        store=True,
        readonly=False,
        currency_field='currency_id',
        help='هذا الحقل مرادف لـ service_charge. تم الاحتفاظ به للتوافق مع الإصدارات السابقة.'
    )
    min_charge = fields.Monetary('الحد الأدنى للفوترة', default=0.0, currency_field='currency_id')
    max_charge = fields.Monetary('الحد الأقصى للفوترة', default=0.0, currency_field='currency_id')
    effective_date = fields.Date('تاريخ السريان')
    end_date = fields.Date('تاريخ الانتهاء')
    is_active = fields.Boolean('فعّال', compute='_compute_is_active', store=True)

    # رسوم محلية (معلم/نظافة/مجلس محلي) — تُحسب على أساس الاستهلاك
    local_fee_per_kwh = fields.Monetary('رسم محلي لكل kWh (افتراضي)', default=0.0, currency_field='currency_id',
        help='السعر الموحد للرسوم المحلية عند استخدام نوع بند العداد = رسوم محلية')
    local_fee_mu_allim = fields.Monetary('رسم المعلم لكل kWh', default=0.0, currency_field='currency_id')
    local_fee_cleaning = fields.Monetary('رسم النظافة لكل kWh', default=0.0, currency_field='currency_id')

    # خصم الدعم — أول N وحدة تُخصم على الجهة الداعمة
    sponsor_id = fields.Many2one('res.partner', string='الجهة الداعمة', help='الجهة التي سيتم تقييد الخصم عليها')
    discount_formula_id = fields.Many2one('utility.formula', string='معادلة الخصم',
        help='معادلة ديناميكية لحساب كمية الخصم')
    discount_block_ids = fields.One2many('utility.contract.template.block', 'template_id',
        domain=[('is_discount', '=', True)], string='شرائح الخصم التدريجية', copy=True)

    # شرائح التسعير: tier = شريحة واحدة لكامل الاستهلاك، block = توزيع تصاعدي على الشرائح.
    block_ids = fields.One2many('utility.contract.template.block', 'template_id',
        domain=[('is_discount', '=', False)], string='شرائح التسعير', copy=True)
    history_ids = fields.One2many('utility.contract.template.history', 'template_id',
        string='سجل التغييرات', readonly=True)

    # سير العمل الآلي
    sale_autoconfirm = fields.Boolean(default=True, string='تأكيد أمر البيع تلقائياً')
    create_invoice_automatically = fields.Boolean(default=True, string='إنشاء الفاتورة تلقائياً')
    validate_invoice_automatically = fields.Boolean(default=False, string='التحقق من الفاتورة تلقائياً')

    # الدفع التلقائي
    is_auto_pay = fields.Boolean(string='دفع تلقائي')
    auto_pay_retries = fields.Integer('عدد محاولات الدفع الافتراضي', default=3)
    auto_pay_retry_hours = fields.Integer('ساعات الانتظار بين المحاولات', default=1)
    active = fields.Boolean('نشط', default=True)

    _sql_constraints = [
        # FIX: منع تكرار رمز القالب داخل نفس الشركة
        ('unique_code_company',
         'unique(code, company_id)',
         'رمز قالب العقد موجود مسبقاً في هذه الشركة. يجب أن يكون الرمز فريداً.'),
    ]

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

    # ── FIX: قيود منطقية على التسعير ────────────────────────────────────────────
    @api.constrains('min_charge', 'max_charge')
    def _check_min_max_charge(self):
        for r in self:
            if r.min_charge and r.max_charge and r.min_charge > r.max_charge:
                raise ValidationError(
                    'الحد الأدنى للفوترة (%.2f) يجب أن يكون أقل من '
                    'الحد الأقصى (%.2f).'
                    % (r.min_charge, r.max_charge)
                )

    @api.constrains('price_per_kwh', 'service_charge')
    def _check_positive_prices(self):
        for r in self:
            if r.price_per_kwh < 0:
                raise ValidationError('سعر الكيلووات/ساعة لا يمكن أن يكون سالباً.')
            if r.service_charge < 0:
                raise ValidationError('رسم الخدمة الثابت لا يمكن أن يكون سالباً.')

    def _get_pricing_blocks(self):
        self.ensure_one()
        return self.env['utility.contract.template.block'].search([
            ('template_id', '=', self.id),
            ('is_discount', '=', False),
        ], order='from_kwh asc, sequence asc, id asc')

    def _get_discount_blocks(self):
        self.ensure_one()
        return self.env['utility.contract.template.block'].search([
            ('template_id', '=', self.id),
            ('is_discount', '=', True),
        ], order='from_kwh asc, sequence asc, id asc')

    def _validate_contract_template_tiers(self):
        """Validate complete pricing and discount tier configuration."""
        for rec in self:
            pricing_blocks = rec._get_pricing_blocks()
            discount_blocks = rec._get_discount_blocks()
            pricing_label = dict(rec._fields['pricing_mode'].selection).get(rec.pricing_mode)

            if rec.pricing_mode in ('tier', 'block'):
                if not pricing_blocks:
                    raise ValidationError(
                        _("نمط التسعير '%s' يتطلب تعريف شرائح تسعير مرتبة على قالب العقد '%s'.")
                        % (pricing_label, rec.name)
                    )

            has_discount_line = rec.line_ids.filtered(lambda line: line.meter_line_type == 'discount')
            if rec.discount_formula_id and has_discount_line:
                if not discount_blocks:
                    raise ValidationError(
                        _("قالب العقد '%s' يحتوي خصم دعم بمعادلة، لذلك يجب تعريف شرائح الخصم التصاعدية.")
                        % rec.name
                    )


    @api.constrains('pricing_mode', 'discount_formula_id', 'block_ids', 'discount_block_ids', 'line_ids')
    def _check_contract_template_tiers(self):
        if self.env.context.get('install_mode') or self.env.context.get('install_module'):
            return
        self._validate_contract_template_tiers()

    @api.constrains('subscriber_category_ids', 'subscriber_ids')
    def _check_categories_and_types_compatibility(self):
        for rec in self:
            if not rec.subscriber_category_ids:
                raise ValidationError(_('يجب اختيار فئات المشتركين الرئيسية لقالب العقد!'))
            if not rec.subscriber_ids:
                raise ValidationError(_('يجب اختيار انواع المشتركين لقالب العقد!'))
            for sub in rec.subscriber_ids:
                if sub.category_id not in rec.subscriber_category_ids:
                    raise ValidationError(
                        _("نوع المشترك '%s' لا يتبع أي من فئات المشتركين الرئيسية المحددة لقالب العقد.")
                        % sub.name
                    )

    @api.constrains('scope', 'region_ids', 'area_ids')
    def _check_scope_regions(self):
        for rec in self:
            if rec.scope == 'restricted' and not rec.region_ids and not rec.area_ids:
                raise ValidationError(_("يجب اختيار منطقة رئيسية أو منطقة فرعية واحدة على الأقل عند تحديد نطاق التغطية كمخصص!"))

    def write(self, vals):
        """عند تغيير الأسعار الرئيسية، سجّل التاريخ تلقائياً."""
        price_fields = {'price_per_kwh', 'service_charge'}
        needs_history = bool(price_fields & set(vals))

        # التقاط القيم القديمة قبل الكتابة
        old_prices = {}
        if needs_history:
                old_prices = {
                r.id: {
                    'price_per_kwh': r.price_per_kwh,
                    'service_charge': r.service_charge,
                }
                for r in self
            }

        res = super().write(vals)

        # تسجيل التاريخ إذا تغيرت الأسعار
        if needs_history:
            for r in self:
                old = old_prices.get(r.id, {})
                new_price = vals.get('price_per_kwh', old.get('price_per_kwh', r.price_per_kwh))
                new_service = vals.get('service_charge', old.get('service_charge', r.service_charge))
                if (old.get('price_per_kwh') != new_price or
                        old.get('service_charge') != new_service):
                    self.env['utility.contract.template.history'].create({
                        'template_id': r.id,
                        'old_price': old.get('price_per_kwh', 0),
                        'new_price': new_price,
                        'old_service_charge': old.get('service_charge', 0),
                        'new_service_charge': new_service,
                        'changed_by': self.env.user.id,
                        'reason': 'تغيير تلقائي عبر النموذج',
                    })
        return res

    def action_sync_lines_with_template(self):
        # البحث عن المنتجات الافتراضية
        Product = self.env['product.product']
        kwh_product = (
            self.env.ref('utility_core.utility_product_kwh', raise_if_not_found=False)
            or Product.search([('type', '=', 'service')], limit=1)
        )
        service_product = (
            self.env.ref('utility_core.utility_product_service_charge', raise_if_not_found=False)
            or Product.search([('type', '=', 'service')], limit=1)
        )
        discount_product = (
            self.env.ref('utility_core.utility_product_discount', raise_if_not_found=False)
            or Product.search([('name', 'like', 'خصم')], limit=1)
            or service_product
        )

        # FIX: التحقق من وجود المنتجات قبل إنشاء البنود
        if not kwh_product:
            raise ValidationError(
                'لا يوجد منتج kWh محدد. المسار: '
                'utility_core.utility_product_kwh أو أي منتج خدمة.'
            )

        for template in self:
            existing_types = template.line_ids.mapped('meter_line_type')

            # مزامنة أو إنشاء بند الاستهلاك
            if 'consumption' not in existing_types and template.price_per_kwh > 0:
                self.env['utility.contract.template.line'].create({
                    'template_id': template.id,
                    'sequence': 10,
                    'product_id': kwh_product.id if kwh_product else False,
                    'name': 'استهلاك كهرباء',
                    'price_type': 'meter_reading',
                    'meter_line_type': 'consumption',
                    'specific_price': template.price_per_kwh,
                })

            # مزامنة أو إنشاء بند رسم الخدمة الثابت
            if 'service_charge' not in existing_types and template.service_charge > 0:
                self.env['utility.contract.template.line'].create({
                    'template_id': template.id,
                    'sequence': 25,
                    'product_id': service_product.id if service_product else False,
                    'name': 'رسوم خدمات إضافية',
                    'price_type': 'fixed',
                    'meter_line_type': 'service_charge',
                    'specific_price': template.service_charge,
                })

            # المعلم
            if 'mu_allim' not in existing_types and template.local_fee_mu_allim > 0:
                mu_allim_prod = template.company_id.mu_allim_product_id or service_product
                self.env['utility.contract.template.line'].create({
                    'template_id': template.id,
                    'sequence': 30,
                    'product_id': mu_allim_prod.id,
                    'name': 'رسم المعلم',
                    'price_type': 'meter_reading',
                    'meter_line_type': 'mu_allim',
                    'specific_price': template.local_fee_mu_allim,
                })

            # النظافة
            if 'cleaning' not in existing_types and template.local_fee_cleaning > 0:
                cleaning_prod = template.company_id.cleaning_product_id or service_product
                self.env['utility.contract.template.line'].create({
                    'template_id': template.id,
                    'sequence': 35,
                    'product_id': cleaning_prod.id,
                    'name': 'رسم النظافة',
                    'price_type': 'meter_reading',
                    'meter_line_type': 'cleaning',
                    'specific_price': template.local_fee_cleaning,
                })

            # المجالس المحلية
            if 'municipality' not in existing_types and template.local_fee_per_kwh > 0:
                muni_prod = template.company_id.local_fee_product_id or service_product
                self.env['utility.contract.template.line'].create({
                    'template_id': template.id,
                    'sequence': 40,
                    'product_id': muni_prod.id,
                    'name': 'رسم المجالس المحلية',
                    'price_type': 'meter_reading',
                    'meter_line_type': 'municipality',
                    'specific_price': template.local_fee_per_kwh,
                })

            # الخصم المدعوم
            if 'discount' not in existing_types and template.discount_formula_id:
                self.env['utility.contract.template.line'].create({
                    'template_id': template.id,
                    'sequence': 45,
                    'product_id': discount_product.id if discount_product else False,
                    'name': 'خصم استهلاك مدعوم',
                    'price_type': 'fixed',
                    'meter_line_type': 'discount',
                    'qty_formula_id': template.discount_formula_id.id,
                    'is_subsidized': True,
                    'specific_price': 0.0,
                })

            # تحديث الأسعار للبنود الحالية لتتطابق تماماً مع بيانات القالب
            for line in template.line_ids:
                if line.meter_line_type == 'consumption':
                    line.specific_price = template.price_per_kwh
                elif line.meter_line_type in ('fixed_fee', 'service_charge'):
                    line.specific_price = template.service_charge
                elif line.meter_line_type == 'mu_allim':
                    line.specific_price = template.local_fee_mu_allim
                elif line.meter_line_type == 'cleaning':
                    line.specific_price = template.local_fee_cleaning
                elif line.meter_line_type == 'municipality':
                    line.specific_price = template.local_fee_per_kwh
                elif line.meter_line_type == 'discount':
                    if template.discount_formula_id:
                        line.qty_formula_id = template.discount_formula_id.id
                        line.specific_price = 0.0

        if len(self) == 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }


class UtilityContractTemplateLine(models.Model):
    _name = 'utility.contract.template.line'
    _description = 'بند قالب العقد'

    template_id = fields.Many2one('utility.contract.template', 'قالب العقد', required=True, ondelete='cascade')
    sequence = fields.Integer('التسلسل', default=10)

    product_id = fields.Many2one('product.product', 'المنتج', required=True)
    name = fields.Text(string='الوصف', translate=True)

    quantity = fields.Float('الكمية', default=1.0)
    uom_id = fields.Many2one('uom.uom', 'وحدة القياس')

    price_type = fields.Selection([
        ('fixed', 'سعر ثابت'),
        ('meter_reading', 'حسب قراءة العداد'),
    ], default='fixed', required=True)

    currency_id = fields.Many2one(
        'res.currency',
        related='template_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )
    specific_price = fields.Monetary('السعر المحدد', currency_field='currency_id')

    # تصنيف البند للفوترة
    meter_line_type = fields.Selection([
        ('consumption', 'الاستهلاك'),
        ('service_charge', 'رسم خدمة ثابت'),
        ('fixed_fee', 'رسم ثابت (قديم)'),
        ('mu_allim', 'رسم المعلم'),
        ('cleaning', 'رسم النظافة'),
        ('municipality', 'رسم المجلس المحلي'),
        ('discount', 'خصم'),
    ], string='نوع بند العداد')

    # الربط مع معادلات محرك الاحتساب
    qty_formula_id = fields.Many2one('utility.formula', 'معادلة الكمية',
        help='معادلة ديناميكية تحسب الكمية تلقائياً (متغيرات: الاستهلاك، قالب العقد، الحساب، الفئة)')
    is_subsidized = fields.Boolean('خصم مدعوم',
        help='يطبق الخصم حسب فئة المشترك — يعمل فقط مع نوع بند العداد = خصم')
