from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import re

PHONE_9_RE = re.compile(r'^\d{9}$')


class UtilityCustomerWizard(models.TransientModel):
    _name = 'utility.customer.wizard'
    _inherit = ['utility.dropdown.mixin']
    _description = 'معالج تسجيل مشترك وعداد موحد'

    name = fields.Char(string='اسم المشترك / الجهة', required=True)
    mobile = fields.Char(string='رقم الجوال', required=True)
    phone = fields.Char(string='رقم الهاتف الثابت')
    national_id = fields.Char(string='الرقم الوطني / الهوية', required=True)
    
    street = fields.Char(string='العنوان (الشارع)')
    city = fields.Char(string='المدينة', default='صنعاء')
    country_id = fields.Many2one('res.country', string='الدولة', default=lambda self: self.env.ref('base.ye', raise_if_not_found=False))

    category_id = fields.Many2one('utility.subscriber.category', string='فئة المشترك الرئيسية', required=True)
    available_subscriber_ids = fields.Many2many('utility.subscriber', compute='_compute_available_subscriber_ids')
    subscriber_id = fields.Many2one('utility.subscriber', string='نوع المشترك', required=True)
    sector_id = fields.Many2one('res.partner.sector', string='القطاع')
    
    available_contract_template_ids = fields.Many2many('utility.contract.template', compute='_compute_available_contract_template_ids')
    contract_template_id = fields.Many2one(
        'utility.contract.template',
        string='قالب العقد الافتراضي',
        required=True,
    )
    
    available_route_ids = fields.Many2many('utility.route', compute='_compute_available_route_ids')
    route_id = fields.Many2one('utility.route', string='مسار القراءة الميداني')

    utility_region_id = fields.Many2one('utility.region', string="المنطقة التشغيلية", domain="[('type', '=', 'region')]")
    available_area_ids = fields.Many2many('utility.region', compute='_compute_available_area_ids')
    utility_area_id = fields.Many2one('utility.region', string="الفرع التشغيلي")
    
    available_zone_ids = fields.Many2many('utility.region', compute='_compute_available_zone_ids')
    transformer_zone_id = fields.Many2one('utility.region', string="نطاق المحول")

    # Private Transformer Fields
    use_private_transformer = fields.Boolean(
        string='محول خاص (المحول للمشترك وحده)',
        default=False,
        help='عند التفعيل: ينشئ المعالج محولاً خاصاً جديداً في utility.transformer ويربطه بالمشترك كخلية خاصة. عدّاد الربط يُنشأ تلقائياً.'
    )
    private_transformer_existing_id = fields.Many2one(
        'utility.transformer', string='محول قائم',
        domain="[('active', '=', True)]",
        help='يمكنك اختيار محول قائم لربطه بهذا المشترك.'
    )
    transformer_name = fields.Char(string='اسم المحول')
    transformer_code = fields.Char(string='كود المحول')
    transformer_capacity = fields.Float(string='السعة (kVA)')
    transformer_phase = fields.Selection([
        ('single', 'أحادي'),
        ('three', 'ثلاثي'),
    ], string='طور المحول')
    transformer_manufacturer = fields.Char(string='الشركة المصنعة للمحول')
    transformer_serial = fields.Char(string='الرقم التسلسلي للمحول')
    voltage_primary = fields.Float(string='الجهد الابتدائي (V)')
    voltage_secondary = fields.Float(string='الجهد الثانوي (V)')
    transformer_substation_id = fields.Many2one('utility.substation', string='المحطة الفرعية')
    transformer_feeder_id = fields.Many2one('utility.feeder', string='المغذي')

    # Optional Meter Creation
    create_meter = fields.Boolean(string='إنشاء وربط عداد جديد فوراً', default=True)
    available_meter_product_ids = fields.Many2many(
        'product.product', compute='_compute_available_meter_product_ids',
        string='منتجات العدادات المتاحة')
    meter_product_id = fields.Many2one('product.product', string='منتج العداد')
    meter_model_id = fields.Many2one('utility.meter.model', string='موديل العداد', readonly=True)
    meter_number = fields.Char(string='رقم العداد', readonly=True, default=lambda self: _('جديد'))
    serial_number = fields.Char(string='الرقم التسلسلي')
    manufacturer = fields.Char(string='الشركة المصنعة', default='Landis+Gyr')
    meter_type_id = fields.Many2one('utility.meter.type', string='نوع العداد')
    payment_type = fields.Selection([
        ('postpaid', 'آجل الدفع'),
        ('prepaid', 'دفع مسبق'),
        ('manual', 'يدوي')
    ], string='نظام العداد', default='manual', required=True)
    sts_key_revision = fields.Char(string='مراجعة مفتاح STS')
    phase = fields.Selection([
        ('single', 'أحادي الطور'),
        ('three', 'ثلاثي الطور'),
    ], string='الطور', default='single')
    communication_type = fields.Selection([
        ('none', 'بدون اتصال'),
        ('ir', 'أشعة تحت الحمراء'),
        ('rf', 'تردد لاسلكي'),
        ('plc', 'ناقل خط الطاقة'),
        ('gsm', 'شبكة الجوال'),
    ], string='نوع الاتصال', default='none')

    def _get_dynamic_domains(self):
        """Return UI domains without relying on helper field names in JS eval."""
        self.ensure_one()
        meter_products = self.env['utility.meter.model'].search([
            ('product_id', '!=', False),
        ]).mapped('product_id')
        area_domain = [('type', '=', 'area')]
        if self.utility_region_id:
            area_domain.append(('parent_id', '=', self.utility_region_id.id))
        zone_domain = [('type', '=', 'zone')]
        if self.utility_area_id:
            zone_domain.append(('parent_id', '=', self.utility_area_id.id))
        return {
            'subscriber_id': self._get_subscriber_domain(self.category_id.id if self.category_id else False),
            'contract_template_id': self._get_contract_template_domain(
                category_id=self.category_id.id if self.category_id else False,
                subscriber_id=self.subscriber_id.id if self.subscriber_id else False,
                region_id=self.utility_region_id.id if self.utility_region_id else False,
                area_id=self.utility_area_id.id if self.utility_area_id else False,
            ),
            'route_id': self._get_route_domain(
                region_id=self.utility_region_id.id if self.utility_region_id else False,
                area_id=self.utility_area_id.id if self.utility_area_id else False,
                zone_id=self.transformer_zone_id.id if self.transformer_zone_id else False,
            ),
            'utility_area_id': area_domain,
            'transformer_zone_id': zone_domain,
            'meter_product_id': [('id', 'in', meter_products.ids)],
        }

    @api.onchange(
        'category_id', 'subscriber_id', 'utility_region_id', 'utility_area_id',
        'transformer_zone_id', 'create_meter'
    )
    def _onchange_dynamic_domains(self):
        for wizard in self:
            return {'domain': wizard._get_dynamic_domains()}

    @api.depends('create_meter')
    def _compute_available_meter_product_ids(self):
        products = self.env['utility.meter.model'].search([
            ('product_id', '!=', False),
        ]).mapped('product_id')
        for wizard in self:
            wizard.available_meter_product_ids = products

    @api.onchange('meter_product_id')
    def _onchange_meter_product_id(self):
        for wizard in self:
            meter_model = False
            if wizard.meter_product_id:
                meter_model = self.env['utility.meter.model'].search([
                    ('product_id', '=', wizard.meter_product_id.id),
                ], limit=1)
                if not meter_model:
                    return {
                        'warning': {
                            'title': _('منتج عداد غير مضبوط'),
                            'message': _('المنتج المختار غير مربوط بموديل عداد. يرجى ضبطه من إعدادات موديلات العدادات.'),
                        }
                    }
            wizard.meter_model_id = meter_model
            wizard.meter_type_id = meter_model.meter_type_id if meter_model else False
            wizard.manufacturer = meter_model.manufacturer if meter_model and meter_model.manufacturer else wizard.manufacturer
            wizard.phase = meter_model.phase if meter_model and meter_model.phase else wizard.phase

    @api.depends('category_id')
    def _compute_available_subscriber_ids(self):
        for rec in self:
            domain = self._get_subscriber_domain(rec.category_id.id if rec.category_id else False)
            rec.available_subscriber_ids = self.env['utility.subscriber'].search(domain)

    @api.depends('category_id', 'subscriber_id', 'utility_region_id', 'utility_area_id')
    def _compute_available_contract_template_ids(self):
        for rec in self:
            domain = self._get_contract_template_domain(
                category_id=rec.category_id.id if rec.category_id else False,
                subscriber_id=rec.subscriber_id.id if rec.subscriber_id else False,
                region_id=rec.utility_region_id.id if rec.utility_region_id else False,
                area_id=rec.utility_area_id.id if rec.utility_area_id else False,
            )
            rec.available_contract_template_ids = self.env['utility.contract.template'].search(domain)

    @api.depends('utility_region_id', 'utility_area_id', 'transformer_zone_id')
    def _compute_available_route_ids(self):
        for rec in self:
            domain = self._get_route_domain(
                region_id=rec.utility_region_id.id if rec.utility_region_id else False,
                area_id=rec.utility_area_id.id if rec.utility_area_id else False,
                zone_id=rec.transformer_zone_id.id if rec.transformer_zone_id else False,
            )
            rec.available_route_ids = self.env['utility.route'].search(domain)

    @api.depends('utility_region_id')
    def _compute_available_area_ids(self):
        for rec in self:
            domain = [('type', '=', 'area')]
            if rec.utility_region_id:
                domain.append(('parent_id', '=', rec.utility_region_id.id))
            rec.available_area_ids = self.env['utility.region'].search(domain)

    @api.depends('utility_area_id')
    def _compute_available_zone_ids(self):
        for rec in self:
            domain = [('type', '=', 'zone')]
            if rec.utility_area_id:
                domain.append(('parent_id', '=', rec.utility_area_id.id))
            rec.available_zone_ids = self.env['utility.region'].search(domain)

    def _find_matching_contract_template(self):
        self.ensure_one()
        if self.subscriber_id and self.subscriber_id.default_contract_template_id:
            default_template = self.subscriber_id.default_contract_template_id
            if default_template in self.available_contract_template_ids:
                return default_template
        if self.available_contract_template_ids:
            return self.available_contract_template_ids[0]
        return self.env['utility.contract.template']

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.subscriber_id and self.subscriber_id not in self.available_subscriber_ids:
            self.subscriber_id = False
        if not self.subscriber_id and len(self.available_subscriber_ids) == 1:
            self.subscriber_id = self.available_subscriber_ids[0]

    @api.onchange('category_id', 'subscriber_id', 'utility_region_id', 'utility_area_id')
    def _onchange_contract_template_cascade(self):
        if self.contract_template_id and self.contract_template_id not in self.available_contract_template_ids:
            self.contract_template_id = False
        if not self.contract_template_id and self.subscriber_id:
            self.contract_template_id = self._find_matching_contract_template()

    @api.onchange('utility_region_id')
    def _onchange_utility_region_id(self):
        if self.utility_area_id and self.utility_area_id not in self.available_area_ids:
            self.utility_area_id = False

    @api.onchange('utility_area_id')
    def _onchange_utility_area_id(self):
        if self.transformer_zone_id and self.transformer_zone_id not in self.available_zone_ids:
            self.transformer_zone_id = False
        if self.route_id and self.route_id not in self.available_route_ids:
            self.route_id = False

    @api.onchange('transformer_zone_id')
    def _onchange_transformer_zone_id(self):
        if self.route_id and self.route_id not in self.available_route_ids:
            self.route_id = False

    @api.onchange('use_private_transformer', 'name', 'national_id')
    def _onchange_use_private_transformer(self):
        if self.use_private_transformer:
            if not self.transformer_name and self.name:
                self.transformer_name = f"محول خاص - {self.name}"
            if not self.transformer_code and self.national_id:
                self.transformer_code = f"PRV-{self.national_id}"

    @api.onchange('transformer_feeder_id')
    def _onchange_transformer_feeder_id(self):
        substation = self.transformer_feeder_id.substation_id
        if substation and substation.zone_id:
            self.transformer_zone_id = substation.zone_id

    @api.constrains('mobile', 'phone')
    def _check_phone_9_digits(self):
        for rec in self:
            if rec.mobile and not PHONE_9_RE.match(rec.mobile):
                raise ValidationError(
                    'رقم الجوال يجب أن يتكون من 9 أرقام فقط، بدون مفتاح دولة (+967/00) أو شرطات.'
                )
            if rec.phone and not PHONE_9_RE.match(rec.phone):
                raise ValidationError(
                    'رقم الهاتف يجب أن يتكون من 9 أرقام فقط، بدون مفتاح دولة (+967/00) أو شرطات.'
                )

    @api.constrains('contract_template_id', 'category_id', 'subscriber_id', 'utility_region_id', 'utility_area_id')
    def _check_wizard_contract_template_compatibility(self):
        for rec in self:
            template = rec.contract_template_id
            if template and rec.category_id and rec.category_id not in template.subscriber_category_ids:
                raise ValidationError(
                    _("قالب العقد '%s' لا يدعم فئة المشترك الرئيسية '%s'.")
                    % (template.name, rec.category_id.name)
                )
            if template and rec.subscriber_id and rec.subscriber_id not in template.subscriber_ids:
                raise ValidationError(
                    _("قالب العقد '%s' لا يدعم نوع المشترك '%s'.")
                    % (template.name, rec.subscriber_id.name)
                )
            if template and template.scope == 'restricted':
                allowed_region_ids = template.region_ids.ids
                allowed_area_ids = template.area_ids.ids
                
                region_id = rec.utility_region_id.id
                area_id = rec.utility_area_id.id
                
                is_region_allowed = region_id in allowed_region_ids if region_id else False
                is_area_allowed = area_id in allowed_area_ids if area_id else False
                
                if not (is_region_allowed or is_area_allowed):
                    raise ValidationError(
                        _("قالب العقد الافتراضي المختار '%s' لا يدعم المنطقة أو المنطقة الفرعية المحددة.")
                        % template.name
                    )

    def _get_or_create_private_transformer(self, partner):
        if self.private_transformer_existing_id:
            t = self.private_transformer_existing_id
            if len(t.customer_ids) > 0:
                raise ValidationError('المحول المختار مرتبط بمشتركين مسبقاً.')
            return t

        if not self.transformer_code:
            raise ValidationError(_('يجب إدخال كود المحول الخاص.'))

        if self.env['utility.transformer'].search([('code', '=', self.transformer_code)], limit=1):
            raise ValidationError(_('كود المحول مستخدم بالفعل.'))

        return self.env['utility.transformer'].create({
            'name': self.transformer_name or f"محول خاص - {partner.name}",
            'code': self.transformer_code,
            'capacity': self.transformer_capacity,
            'phase': self.transformer_phase or (self.phase if self.phase else 'single'),
            'manufacturer': self.transformer_manufacturer,
            'serial_number': self.transformer_serial,
            'voltage_primary': self.voltage_primary,
            'voltage_secondary': self.voltage_secondary,
            'substation_id': self.transformer_substation_id.id if self.transformer_substation_id else False,
            'feeder_id': self.transformer_feeder_id.id if self.transformer_feeder_id else False,
            'zone_region_id': self.transformer_zone_id.id if self.transformer_zone_id else False,
            'is_private': True,
        })

    def action_create_customer(self):
        self.ensure_one()
        if not self.create_meter:
            raise ValidationError(_('يجب تفعيل إنشاء العداد قبل حفظ المشترك.'))
        if not self.meter_product_id:
            raise ValidationError(_('يجب اختيار منتج العداد قبل حفظ المشترك.'))
        if not self.serial_number:
            raise ValidationError(_('يجب إدخال الرقم التسلسلي للعداد قبل حفظ المشترك.'))
        if self.meter_product_id and not self.meter_model_id:
            raise ValidationError(_('منتج العداد المختار غير مربوط بموديل عداد. يرجى ضبط موديلات العدادات أولاً.'))
        if self.env['utility.meter'].search([('serial_number', '=', self.serial_number)], limit=1):
            raise ValidationError(_('الرقم التسلسلي للعداد مستخدم مسبقاً. يرجى إدخال رقم تسلسلي مختلف.'))

        if self.subscriber_id and self.category_id and self.subscriber_id.category_id != self.category_id:
            raise ValidationError(
                _("نوع المشترك '%s' يجب أن ينتمي إلى فئة المشترك الرئيسية المحددة '%s'.")
                % (self.subscriber_id.name, self.category_id.name)
            )

        if self.contract_template_id:
            if self.category_id and self.category_id not in self.contract_template_id.subscriber_category_ids:
                raise ValidationError(
                    _("قالب العقد '%s' لا يدعم فئة المشترك الرئيسية '%s'.")
                    % (self.contract_template_id.name, self.category_id.name)
                )
            if self.subscriber_id and self.subscriber_id not in self.contract_template_id.subscriber_ids:
                raise ValidationError(
                    _("قالب العقد '%s' لا يدعم نوع المشترك '%s'.")
                    % (self.contract_template_id.name, self.subscriber_id.name)
                )
            if self.contract_template_id.scope == 'restricted':
                allowed_region_ids = self.contract_template_id.region_ids.ids
                allowed_area_ids = self.contract_template_id.area_ids.ids
                
                region_id = self.utility_region_id.id
                area_id = self.utility_area_id.id
                
                is_region_allowed = region_id in allowed_region_ids if region_id else False
                is_area_allowed = area_id in allowed_area_ids if area_id else False
                
                if not (is_region_allowed or is_area_allowed):
                    raise ValidationError(
                        _("قالب العقد المختار '%s' مخصص لمناطق محددة ولا يدعم المنطقة أو المنطقة الفرعية المحددة.")
                        % self.contract_template_id.name
                    )

        # 1. Create res.partner
        partner_vals = {
            'name': self.name,
            'mobile': self.mobile,
            'phone': self.phone,
            'street': self.street,
            'city': self.city,
            'country_id': self.country_id.id if self.country_id else False,
            'is_subscriber': True,
            'subscriber_id': self.subscriber_id.id,
            'sector_id': self.sector_id.id if self.sector_id else False,
            'region_id': self.utility_region_id.id if self.utility_region_id else False,
            'area_id': self.utility_area_id.id if self.utility_area_id else False,
            'zone_id': self.transformer_zone_id.id if self.transformer_zone_id else False,
        }
        partner = self.env['res.partner'].create(partner_vals)

        # 2. Handle Private Transformer before customer creation
        transformer = False
        if self.use_private_transformer:
            transformer = self._get_or_create_private_transformer(partner)

        # 3. Create utility.meter before customer because meter_id is required
        status_active = self.env['utility.meter.status'].search([('code', '=', 'ACTIVE')], limit=1)
        meter_vals = {
            'serial_number': self.serial_number,
            'manufacturer': self.manufacturer,
            'model_id': self.meter_model_id.id if self.meter_model_id else False,
            'meter_type_id': self.meter_type_id.id if self.meter_type_id else False,
            'status_id': status_active.id if status_active else False,
            'phase': self.phase,
            'transformer_id': transformer.id if transformer else False,
            'feeder_id': transformer.feeder_id.id if transformer and transformer.feeder_id else False,
            'payment_type': self.payment_type,
            'sts_key_revision': self.sts_key_revision if self.payment_type == 'prepaid' else False,
            'communication_type': self.communication_type if self.payment_type == 'postpaid' else False,
        }
        if 'product_id' in self.env['utility.meter']._fields:
            meter_vals['product_id'] = self.meter_product_id.id
        meter = self.env['utility.meter'].create(meter_vals)

        # 4. Create utility.customer
        customer_vals = {
            'partner_id': partner.id,
            'national_id': self.national_id,
            'category_id': self.category_id.id,
            'subscriber_id': self.subscriber_id.id,
            'contract_template_id': self.contract_template_id.id,
            'route_id': self.route_id.id if self.route_id else False,
            'state': 'active',
            'contract_state': 'active',
            'meter_id': meter.id,
            'transformer_id': transformer.id if transformer else False,
            'cell_id': transformer.feeder_id.id if transformer and transformer.feeder_id else False,
        }
        customer = self.env['utility.customer'].create(customer_vals)
        meter.write({'customer_id': customer.id})

        # 5. Link meter as coupling meter for the private transformer
        if transformer and meter:
            transformer.write({'coupling_meter_id': meter.id})

        # 6. Return action to open the newly created customer form
        return {
            'name': _('بطاقة المشترك'),
            'type': 'ir.actions.act_window',
            'res_model': 'utility.customer',
            'view_mode': 'form',
            'res_id': customer.id,
            'target': 'current',
        }
