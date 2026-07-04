from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import re

PHONE_9_RE = re.compile(r'^\d{9}$')


class UtilityCustomerWizard(models.TransientModel):
    _name = 'utility.customer.wizard'
    _description = 'معالج تسجيل مشترك وعداد موحد (Unified Subscriber Wizard)'

    name = fields.Char(string='اسم المشترك / الجهة', required=True)
    mobile = fields.Char(string='رقم الجوال', required=True)
    phone = fields.Char(string='رقم الهاتف الثابت')
    national_id = fields.Char(string='الرقم الوطني / الهوية', required=True)
    
    street = fields.Char(string='العنوان (الشارع)')
    city = fields.Char(string='المدينة', default='صنعاء')
    country_id = fields.Many2one('res.country', string='الدولة', default=lambda self: self.env.ref('base.ye', raise_if_not_found=False))

    category_id = fields.Many2one('utility.subscriber.category', string='الفئة (نوع الحساب)', required=True)

    subscriber_id = fields.Many2one('utility.subscriber', string='نوع المشترك', required=True)
    sector_id = fields.Many2one('res.partner.sector', string='القطاع')
    contract_template_id = fields.Many2one('utility.contract.template', string='قالب العقد الافتراضي', required=True)
    route_id = fields.Many2one('utility.route', string='مسار القراءة الميداني')

    utility_region_id = fields.Many2one('utility.region', string="المنطقة التشغيلية (Region)", domain="[('type', '=', 'region')]")
    utility_area_id = fields.Many2one('utility.region', string="الفرع التشغيلي (Area)", domain="[('type', '=', 'area')]")
    transformer_zone_id = fields.Many2one('utility.region', string="نطاق المحول (Zone)", domain="[('type', '=', 'zone')]")

    # Private Transformer Fields
    use_private_transformer = fields.Boolean(
        string='محول خاص (المحول للمشترك وحده)',
        default=False,
        help='عند التفعيل: ينشئ الـ wizard محولاً خاصاً جديداً في utility.transformer ويربطه بالمشترك كخلية خاصة. عدّاد الربط يُنشأ تلقائياً.'
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
    meter_number = fields.Char(string='رقم العداد (Meter Number)')
    serial_number = fields.Char(string='الرقم التسلسلي للعداد (Serial)')
    manufacturer = fields.Char(string='الشركة المصنعة', default='Landis+Gyr')
    meter_type_id = fields.Many2one('utility.meter.type', string='نوع العداد')
    payment_type = fields.Selection([
        ('postpaid', 'آجل الدفع (عن بُعد / ذكي)'),
        ('prepaid', 'دفع مسبق (Prepaid)'),
        ('manual', 'يدوي (Manual)')
    ], string='نظام العداد', default='manual', required=True)
    sts_key_revision = fields.Char(string='STS Key Revision')
    phase = fields.Selection([
        ('single', 'أحادي الطور (Single Phase)'),
        ('three', 'ثلاثي الطور (Three Phase)'),
    ], string='الطور (Phase)', default='single')
    communication_type = fields.Selection([
        ('none', 'بدون اتصال'),
        ('ir', 'أشعة تحت الحمراء (IR)'),
        ('rf', 'تردد لاسلكي (RF)'),
        ('plc', 'ناقل خط الطاقة (PLC)'),
        ('gsm', 'شبكة الجوال (GSM/GPRS)'),
    ], string='نوع الاتصال', default='none')

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id:
            # يمكن اختيار أول نوع مشترك ضمن الفئة تلقائياً
            subscriber = self.env['utility.subscriber'].search([('category_id', '=', self.category_id.id)], limit=1)
            contract_template = False
            if subscriber:
                self.subscriber_id = subscriber.id
                contract_template = self.env['utility.contract.template'].search([('subscriber_ids', 'in', self.subscriber_id.id)], limit=1)
            if contract_template:
                self.contract_template_id = contract_template.id

    @api.onchange('use_private_transformer', 'name', 'national_id')
    def _onchange_use_private_transformer(self):
        if self.use_private_transformer:
            if not self.transformer_name and self.name:
                self.transformer_name = f"محول خاص - {self.name}"
            if not self.transformer_code and self.national_id:
                self.transformer_code = f"PRV-{self.national_id}"

    @api.onchange('transformer_feeder_id')
    def _onchange_transformer_feeder_id(self):
        if self.transformer_feeder_id and self.transformer_feeder_id.zone_id:
            self.transformer_zone_id = self.transformer_feeder_id.zone_id

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
        if not self.create_meter or not self.meter_number:
            raise ValidationError(_('يجب إنشاء عداد وإدخال رقم العداد قبل حفظ المشترك.'))

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
            'meter_number': self.meter_number,
            'serial_number': self.serial_number or self.meter_number,
            'manufacturer': self.manufacturer,
            'meter_type_id': self.meter_type_id.id if self.meter_type_id else False,
            'status_id': status_active.id if status_active else False,
            'phase': self.phase,
            'transformer_id': transformer.id if transformer else False,
            'feeder_id': transformer.feeder_id.id if transformer and transformer.feeder_id else False,
            'payment_type': self.payment_type,
            'sts_key_revision': self.sts_key_revision if self.payment_type == 'prepaid' else False,
            'communication_type': self.communication_type if self.payment_type == 'postpaid' else False,
        }
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
