from urllib.parse import quote

import re

from odoo import api, fields, models, _
import base64
from odoo.exceptions import UserError, ValidationError


PHONE_9_RE = re.compile(r'^\d{9}$')


def validate_phone_9(value, field_label='رقم الهاتف'):
    if not value:
        return
    if not PHONE_9_RE.match(value):
        raise ValidationError(
            '%s يجب أن يتكون من 9 أرقام فقط، بدون مفتاح دولة (+967/00) أو شرطات.'
            % field_label
        )


class UtilityMeter(models.Model):
    _name = 'utility.meter'
    _description = 'عداد كهرباء'
    _inherit = ['mail.thread']
    _order = 'meter_number'
    _rec_name = 'meter_number'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    meter_number = fields.Char('رقم العداد', required=True, index=True, default=lambda self: _('جديد'))
    operational_number = fields.Char('الرقم التشغيلي', index=True, tracking=True)
    # المواصفات الفنية مصدر حقيقتها عداد الموديل (utility.meter.model)؛
    # الحقول هنا مجرد إسقاطات للقراءة فقط للتوافق مع الشاشات القديمة.
    manufacturer = fields.Char(
        'الشركة المصنّعة', related='model_id.manufacturer', store=True, readonly=True)
    model_id = fields.Many2one('utility.meter.model', 'الموديل')
    payment_type = fields.Selection([
        ('postpaid', 'آجل الدفع'),
        ('prepaid', 'دفع مسبق'),
        ('manual', 'يدوي')
    ], string='نظام العداد', default='manual', required=True)
    meter_type_id = fields.Many2one('utility.meter.type', 'نوع العداد')
    status_id = fields.Many2one('utility.meter.status', 'الحالة')
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور', help='الطور التشغيلي للعداد؛ يُورث من الموديل عند اختياره')
    voltage = fields.Float(
        'الجهد (فولت)', related='model_id.voltage', store=True, readonly=True)
    current_rating = fields.Float(
        'شدة التيار (أمبير)', related='model_id.current_rating', store=True, readonly=True)
    power_rating = fields.Float(
        'القدرة (كيلوواط)', related='model_id.power_rating', store=True, readonly=True)
    customer_id = fields.Many2one('utility.customer', 'العميل/العقد', index=True)
    account_id = fields.Many2one('utility.customer', string='الحساب', related='customer_id', store=True)

    idle_months = fields.Integer('الأشهر الخاملة', default=0, help='عدد الأشهر المتتالية بدون استهلاك')
    last_calibration_date = fields.Date('تاريخ آخر فحص/معايرة')
    next_calibration_date = fields.Date('تاريخ الفحص القادم')

    region_id = fields.Many2one('utility.region', 'المنطقة', compute='_compute_location_fields', store=True)
    area_id = fields.Many2one('utility.region', 'المنطقة الفرعية', compute='_compute_location_fields', store=True)
    zone_id = fields.Many2one('utility.region', 'المنطقة التفصيلية', compute='_compute_location_fields', store=True)
    route_id = fields.Many2one('utility.route', 'خط السير', compute='_compute_location_fields', store=True)
    transformer_id = fields.Many2one('utility.transformer', 'المحول', compute='_compute_location_fields', store=True)
    substation_id = fields.Many2one('utility.substation', 'المحطة', compute='_compute_location_fields', store=True)
    feeder_id = fields.Many2one('utility.feeder', 'الفيدر', compute='_compute_location_fields', store=True)
    installation_date = fields.Date('تاريخ التركيب')
    address = fields.Text('العنوان')
    reading_ids = fields.One2many('utility.reading', 'meter_id', string='سجل القراءات')
    log_ids = fields.One2many('utility.meter.log', 'meter_id', string='سجل تاريخ العداد')
    reading_count = fields.Integer('عدد القراءات', compute='_compute_reading_count', store=True)
    last_read_date = fields.Datetime('تاريخ آخر قراءة')
    last_reading_value = fields.Float('قيمة آخر قراءة', digits=(12, 3))
    multiplier = fields.Float('معامل الضرب', default=1.0)
    qr_code_value = fields.Char('بيانات QR', compute='_compute_qr_code', readonly=True)
    qr_code_url = fields.Char('رابط QR', compute='_compute_qr_code', readonly=True)
    qr_code_image = fields.Binary('صورة QR', compute='_compute_qr_code', readonly=True, attachment=False)

    # خصائص الربط
    is_coupling_meter = fields.Boolean('عداد ربط رئيسي', default=False, help='يُشير إذا كان هذا العداد هو عداد ربط يقرأ إجمالي طاقة الفيدر أو المحطة')

    # نوع الربط
    connection_type = fields.Selection([
        ('not_connected', 'غير مربوط'),
        ('subscriber', 'مربوط بمشترك'),
        ('private_transformer', 'محول خاص'),
        ('transformer', 'محول'),
        ('feeder', 'فيدر'),
    ], string='نوع الربط', default='not_connected', required=True, tracking=True)

    linked_transformer_id = fields.Many2one(
        'utility.transformer', 'المحول المرتبط', index=True,
        domain="[('is_private', '=', False)]")
    linked_private_transformer_id = fields.Many2one(
        'utility.transformer', 'المحول الخاص', index=True,
        domain="[('is_private', '=', True)]")
    linked_feeder_id = fields.Many2one(
        'utility.feeder', 'Linked Feeder', index=True)

    @api.depends('reading_ids')
    def _compute_reading_count(self):
        for m in self:
            m.reading_count = len(m.reading_ids)

    @api.onchange('model_id')
    def _onchange_model_id(self):
        if not self.model_id:
            return
        model = self.model_id
        if not self.phase:
            self.phase = model.phase
        if not self.meter_type_id:
            self.meter_type_id = model.meter_type_id

    def _update_last_reading(self):
        for m in self:
            last = self.env['utility.reading'].search(
                [('meter_id', '=', m.id)], order='reading_date desc, id desc', limit=1)
            if last:
                m.write({
                    'last_reading_value': last.reading_value,
                    'last_read_date': last.reading_date,
                })

    def _lock_meter(self):
        """Serialize concurrent decisions that involve this meter (e.g. meter
        assignment/installation) by locking its row with SELECT ... FOR UPDATE.
        Must be called inside the same transaction as the decision that reads
        the current assignments and then inserts the new one."""
        self.env.flush_all()
        if self.ids:
            self.env.cr.execute(
                'SELECT id FROM utility_meter WHERE id IN %s ORDER BY id FOR UPDATE',
                [tuple(self.ids)])
        self.invalidate_cache()

    def action_view_readings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('سجل القراءات - %s') % self.meter_number,
            'res_model': 'utility.reading',
            'view_mode': 'tree,form',
            'domain': [('meter_id', '=', self.id)],
            'context': {'default_meter_id': self.id},
        }

    @api.depends('connection_type',
                 'customer_id', 'customer_id.region_id', 'customer_id.area_id', 'customer_id.zone_id',
                 'customer_id.route_id', 'customer_id.transformer_id', 'customer_id.transformer_id.substation_id',
                 'customer_id.cell_id',
                 'linked_transformer_id', 'linked_transformer_id.substation_id', 'linked_transformer_id.feeder_id',
                 'linked_transformer_id.zone_region_id',
                 'linked_private_transformer_id', 'linked_private_transformer_id.substation_id',
                 'linked_private_transformer_id.feeder_id', 'linked_private_transformer_id.zone_region_id',
                 'linked_feeder_id', 'linked_feeder_id.substation_id')
    def _compute_location_fields(self):
        for m in self:
            ct = m.connection_type
            if ct == 'subscriber' and m.customer_id:
                m.region_id = m.customer_id.region_id
                m.area_id = m.customer_id.area_id
                m.zone_id = m.customer_id.zone_id
                m.route_id = m.customer_id.route_id
                m.transformer_id = m.customer_id.transformer_id
                m.substation_id = m.transformer_id.substation_id if m.transformer_id else False
                m.feeder_id = m.customer_id.cell_id
            elif ct == 'private_transformer' and m.linked_private_transformer_id:
                t = m.linked_private_transformer_id
                m.region_id = t.region_id
                m.area_id = t.area_id
                m.zone_id = t.zone_region_id
                m.route_id = False
                m.transformer_id = t
                m.substation_id = t.substation_id
                m.feeder_id = t.feeder_id
            elif ct == 'transformer' and m.linked_transformer_id:
                t = m.linked_transformer_id
                m.region_id = t.region_id
                m.area_id = t.area_id
                m.zone_id = t.zone_region_id
                m.route_id = False
                m.transformer_id = t
                m.substation_id = t.substation_id
                m.feeder_id = t.feeder_id
            elif ct == 'feeder' and m.linked_feeder_id:
                f = m.linked_feeder_id
                m.region_id = f.region_id
                m.area_id = f.area_id
                m.zone_id = False
                m.route_id = False
                m.transformer_id = False
                m.substation_id = f.substation_id
                m.feeder_id = f
            else:
                m.region_id = False
                m.area_id = False
                m.zone_id = False
                m.route_id = False
                m.transformer_id = False
                m.substation_id = False
                m.feeder_id = False

    @api.depends('meter_number', 'operational_number', 'connection_type',
                 'customer_id.customer_number', 'customer_id.partner_id.name',
                 'linked_transformer_id.code', 'linked_private_transformer_id.code',
                 'linked_feeder_id.code',
                 'transformer_id.code', 'feeder_id.code')
    def _compute_qr_code(self):
        for meter in self:
            customer_name = ''
            customer_number = ''
            if meter.customer_id:
                customer_number = meter.customer_id.customer_number or ''
                customer_name = meter.customer_id.partner_id.name or ''
            company_name = (meter.company_id.name if meter.company_id else self.env.company.name) or ''
            payload = '|'.join([
                'UTILITY-METER',
                company_name,
                meter.meter_number or '',
                meter._get_physical_serial(),
                customer_number,
                customer_name,
                meter.transformer_id.code or '',
                meter.feeder_id.code or '',
                meter.operational_number or '',
            ])
            meter.qr_code_value = payload
            encoded = quote(payload)
            base_url = self.env['ir.config_parameter'].sudo().get_param(
                'report.url') or self.env['ir.config_parameter'].sudo().get_param(
                'web.base.url', 'http://localhost:8069')
            meter.qr_code_url = '%s/report/barcode?barcode_type=QR&value=%s&width=%s&height=%s' % (
                base_url.rstrip('/'), encoded, 200, 200)
            try:
                barcode = self.env['ir.actions.report'].barcode('QR', payload, width=200, height=200)
                meter.qr_code_image = base64.b64encode(barcode)
            except Exception:
                meter.qr_code_image = False
    _sql_constraints = [
        ('unique_meter_number_company', 'unique(meter_number, company_id)',
         'رقم العداد يجب أن يكون فريداً لكل شركة!'),
        ('unique_operational_number_company', 'unique(operational_number, company_id)',
         'الرقم التشغيلي للعداد يجب أن يكون فريداً لكل شركة!'),
    ]

    def action_add_subscriber(self):
        self.ensure_one()
        if self.connection_type != 'not_connected' or self.customer_id:
            raise UserError(_('هذا العداد مرتبط بالفعل بمشترك (%s) أو بعنصر آخر.') % (self.customer_id.display_name if self.customer_id else self.connection_type))
        return {
            'type': 'ir.actions.act_window',
            'name': _('إضافة مشترك جديد'),
            'res_model': 'utility.meter.subscriber.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_meter_id': self.id},
        }

    def action_add_private_transformer(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('إضافة محول خاص'),
            'res_model': 'utility.meter.private.transformer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_meter_id': self.id},
        }

    def action_add_transformer(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('إضافة محول'),
            'res_model': 'utility.meter.transformer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_meter_id': self.id},
        }

    def action_add_feeder(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('إضافة فيدر / خلية'),
            'res_model': 'utility.meter.feeder.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_meter_id': self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'operational_number' in vals:
                vals['operational_number'] = (vals['operational_number'] or '').strip() or False
            if vals.get('meter_number', _('جديد')) == _('جديد'):
                vals['meter_number'] = self.env['ir.sequence'].next_by_code('utility.meter') or _('جديد')
        return super().create(vals_list)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = self._name_search_domain(name, operator)
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)

    def _get_physical_serial(self):
        """Return the physical serial when an inventory bridge provides it."""
        self.ensure_one()
        return ''

    @api.model
    def _name_search_domain(self, name, operator='ilike'):
        """Build the logical meter lookup domain without inventory fields."""
        if not name:
            return []
        return ['|', '|', '|',
            ('meter_number', operator, name),
            ('operational_number', operator, name),
            ('customer_id.partner_id.name', operator, name),
            ('meter_type_id.name', operator, name),
        ]

    @api.model
    def _scan_domain(self, value):
        """Build the barcode lookup domain; inventory may add Lot/Serial."""
        return [('meter_number', '=', value)]

    @api.depends('connection_type', 'meter_number', 'operational_number', 'customer_id', 'customer_id.partner_id', 'linked_private_transformer_id', 'linked_transformer_id', 'transformer_id', 'linked_feeder_id', 'feeder_id', 'meter_type_id', 'payment_type')
    def _compute_display_name(self):
        for meter in self:
            parts = [
                f"[{meter.operational_number}] {meter.meter_number}"
                if meter.operational_number else f"[{meter.meter_number}]"
            ]

            # 1. اسم العنصر المرتبط حسب نوع الربط (مشترك / محول خاص / محول / فيدر)
            target_name = False
            ct = getattr(meter, 'connection_type', False)
            if ct == 'subscriber' and meter.customer_id and meter.customer_id.partner_id:
                target_name = meter.customer_id.partner_id.name
            elif ct == 'private_transformer' and meter.linked_private_transformer_id:
                target_name = meter.linked_private_transformer_id.name
            elif ct == 'transformer' and (meter.linked_transformer_id or meter.transformer_id):
                target_name = (meter.linked_transformer_id or meter.transformer_id).name
            elif ct == 'feeder' and (meter.linked_feeder_id or meter.feeder_id):
                target_name = (meter.linked_feeder_id or meter.feeder_id).name
            elif not ct and meter.customer_id and meter.customer_id.partner_id:
                target_name = meter.customer_id.partner_id.name

            if target_name:
                parts.append(target_name)

            # 2. نوع العداد
            type_name = False
            if meter.meter_type_id and meter.meter_type_id.name:
                type_name = meter.meter_type_id.name
            elif meter.payment_type:
                type_name = dict(meter._fields['payment_type'].selection).get(meter.payment_type)

            if type_name:
                parts.append(type_name)

            meter.display_name = " - ".join(parts)

    def name_get(self):
        return [(meter.id, meter.display_name or f"[{meter.meter_number}]") for meter in self]

    def write(self, vals):
        vals = dict(vals)
        if 'operational_number' in vals:
            vals['operational_number'] = (vals['operational_number'] or '').strip() or False
        for meter in self:
            if not self.env.context.get('skip_implicit_log'):
                if 'status_id' in vals and vals.get('status_id') != meter.status_id.id:
                    new_status = self.env['utility.meter.status'].browse(vals['status_id']) if vals.get('status_id') else None
                    desc = f"تغيرت حالة العداد من {meter.status_id.name if meter.status_id else 'غير محدد'} إلى {new_status.name if new_status else 'غير محدد'}"
                    if 'utility.meter.log' in self.env:
                        self.env['utility.meter.log'].with_context(allow_log_update=True)._create_log(
                            meter.id, 'status_change', desc, customer_id=meter.customer_id
                        )
                if 'customer_id' in vals and vals.get('customer_id') != meter.customer_id.id:
                    old_cust = meter.customer_id.display_name if meter.customer_id else 'Undefined'
                    new_cust = self.env['utility.customer'].browse(vals['customer_id']).display_name if vals.get('customer_id') else 'Undefined'
                    desc = f"تم نقل العداد من العميل {old_cust} إلى العميل {new_cust}"
                    if 'utility.meter.log' in self.env:
                        self.env['utility.meter.log'].with_context(allow_log_update=True)._create_log(
                            meter.id, 'transfer', desc, customer_id=vals.get('customer_id')
                        )
        return super().write(vals)


class UtilityMeterType(models.Model):
    _name = 'utility.meter.type'
    _description = 'نوع العداد'
    _order = 'name'

    name = fields.Char('الاسم', required=True)
    code = fields.Char('الرمز', required=True)
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور')
    description = fields.Text('الوصف')


class UtilityMeterModel(models.Model):
    _name = 'utility.meter.model'
    _description = 'موديل العداد'
    _order = 'name'

    name = fields.Char('الاسم', required=True)
    code = fields.Char('Code')
    manufacturer = fields.Char('الشركة المصنّعة')
    meter_type_id = fields.Many2one('utility.meter.type', 'النوع')
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور', help='القدرة الطورية الافتراضية لهذا الموديل')
    voltage = fields.Float('الجهد (فولت)')
    current_rating = fields.Float('شدة التيار (أمبير)')
    power_rating = fields.Float('القدرة (كيلوواط)')
    voltage_range = fields.Char('Voltage Range')
    current_range = fields.Char('Current Range')
    sts_supported = fields.Boolean('يدعم STS')
    communication_types = fields.Char('أنواع الاتصال')
    description = fields.Text('الوصف')
    product_id = fields.Many2one(
        'product.product', 'المنتج',
        help='المنتج الذي يمثل هذا الموديل في نظام المخزون والمحاسبة',
    )

    def action_open_product(self):
        self.ensure_one()
        if self.product_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'المنتج',
                'res_model': 'product.product',
                'res_id': self.product_id.id,
                'view_mode': 'form',
                'target': 'current',
            }


class UtilityMeterStatus(models.Model):
    _name = 'utility.meter.status'
    _description = 'حالة العداد'
    _order = 'sequence, name'

    name = fields.Char('الاسم', required=True)
    code = fields.Char('الرمز', required=True)
    sequence = fields.Integer('التسلسل')
    description = fields.Text('الوصف')
