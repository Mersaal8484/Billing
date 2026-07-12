from urllib.parse import quote

import re

from odoo import api, fields, models, _
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
    serial_number = fields.Char('الرقم التسلسلي', index=True)
    manufacturer = fields.Char('الشركة المصنّعة')
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
    ], string='الطور')
    voltage = fields.Float('الجهد (فولت)')
    current_rating = fields.Float('شدة التيار (أمبير)')
    power_rating = fields.Float('القدرة (كيلوواط)')
    sts_key_revision = fields.Char('مراجعة مفتاح STS')
    customer_id = fields.Many2one('utility.customer', 'العميل/العقد', index=True)
    account_id = fields.Many2one('utility.customer', string='الحساب', related='customer_id', store=True)

    region_id = fields.Many2one('utility.region', 'المنطقة', compute='_compute_location_fields', store=True)
    area_id = fields.Many2one('utility.region', 'المنطقة الفرعية', compute='_compute_location_fields', store=True)
    zone_id = fields.Many2one('utility.region', 'المنطقة التفصيلية', compute='_compute_location_fields', store=True)
    route_id = fields.Many2one('utility.route', 'خط السير', compute='_compute_location_fields', store=True)
    transformer_id = fields.Many2one('utility.transformer', 'المحول', compute='_compute_location_fields', store=True)
    substation_id = fields.Many2one('utility.substation', 'المحطة', compute='_compute_location_fields', store=True)
    feeder_id = fields.Many2one('utility.feeder', 'الفيدر', compute='_compute_location_fields', store=True)
    installation_date = fields.Date('تاريخ التركيب')
    address = fields.Text('العنوان')
    communication_type = fields.Selection([
        ('gsm', 'جي إس إم (GSM)'),
        ('nbiot', 'إن بي آي أو تي (NB-IoT)'),
        ('lora', 'لورا (LoRa)'),
        ('rf', 'تردد لاسلكي (RF)'),
        ('plc', 'خط الطاقة (PLC)'),
        ('manual', 'يدوي'),
    ], string='نوع الاتصال')
    sim_number = fields.Char('رقم شريحة SIM')
    reading_ids = fields.One2many('utility.reading', 'meter_id', string='سجل القراءات')
    log_ids = fields.One2many('utility.meter.log', 'meter_id', string='سجل تاريخ العداد')
    reading_count = fields.Integer('عدد القراءات', compute='_compute_reading_count', store=True)
    last_read_date = fields.Datetime('تاريخ آخر قراءة')
    last_reading_value = fields.Float('قيمة آخر قراءة', digits=(12, 3))
    multiplier = fields.Float('معامل الضرب', default=1.0)
    qr_code_value = fields.Char('بيانات QR', compute='_compute_qr_code', readonly=True)
    qr_code_url = fields.Char('رابط QR', compute='_compute_qr_code', readonly=True)


    # خصائص الربط
    is_coupling_meter = fields.Boolean('عداد ربط رئيسي', default=False, help='يُشير إذا كان هذا العداد هو عداد ربط يقرأ إجمالي طاقة الفيدر أو المحطة')

    @api.depends('reading_ids')
    def _compute_reading_count(self):
        for m in self:
            m.reading_count = len(m.reading_ids)

    def _update_last_reading(self):
        for m in self:
            last = self.env['utility.reading'].search(
                [('meter_id', '=', m.id)], order='reading_date desc, id desc', limit=1)
            if last:
                m.write({
                    'last_reading_value': last.reading_value,
                    'last_read_date': last.reading_date,
                })

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

    @api.depends('customer_id', 'customer_id.region_id', 'customer_id.area_id', 'customer_id.zone_id',
                 'customer_id.route_id', 'customer_id.transformer_id', 'customer_id.transformer_id.substation_id',
                 'customer_id.cell_id')
    def _compute_location_fields(self):
        for m in self:
            m.region_id = m.customer_id.region_id if m.customer_id else False
            m.area_id = m.customer_id.area_id if m.customer_id else False
            m.zone_id = m.customer_id.zone_id if m.customer_id else False
            m.route_id = m.customer_id.route_id if m.customer_id else False
            m.transformer_id = m.customer_id.transformer_id if m.customer_id else False
            m.substation_id = m.transformer_id.substation_id if m.transformer_id else False
            m.feeder_id = m.customer_id.cell_id if m.customer_id else False

    @api.depends('meter_number', 'serial_number', 'customer_id.customer_number', 'customer_id.partner_id.name', 'transformer_id.code', 'feeder_id.code')
    def _compute_qr_code(self):
        for meter in self:
            payload = '|'.join([
                'UTILITY-METER',
                meter.company_id.name or '',
                meter.meter_number or '',
                meter.serial_number or '',
                meter.customer_id.customer_number or '',
                meter.customer_id.partner_id.name or '',
                meter.transformer_id.code or '',
                meter.feeder_id.code or '',
            ])
            meter.qr_code_value = payload
            meter.qr_code_url = '/report/barcode/?type=QR&value=%s' % quote(payload)
    _sql_constraints = [
        ('unique_meter_number_company', 'unique(meter_number, company_id)',
         'رقم العداد يجب أن يكون فريداً لكل شركة!'),
        ('unique_serial_number', 'unique(serial_number)', 'الرقم التسلسلي يجب أن يكون فريداً!'),
    ]

    def action_request_ami_reading(self):
        provider = self.env['utility.integration.provider'].sudo().search([
            ('provider_type', '=', 'ami'),
            ('active', '=', True),
        ], limit=1)
        if not provider:
            raise UserError(_('لا يوجد مزود AMI نشط.'))
        for meter in self:
            payload = {
                'meter_number': meter.meter_number,
                'serial_number': meter.serial_number,
                'customer': meter.customer_id.customer_number if meter.customer_id else False,
            }
            provider.call_json(payload, 'ami.reading.request', record=meter)
        return True

    def create_ami_reading(self, reading_value, reading_date=False, date_range_id=False):
        self.ensure_one()
        return self.env['utility.reading'].sudo().create({
            'meter_id': self.id,
            'reading_value': reading_value,
            'reading_date': reading_date or fields.Datetime.now(),
            'date_range_id': date_range_id or False,
            'reading_type': 'ami',
            'reading_category': 'customer',
            'reading_source': 'ami_integration',
        })
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('meter_number', _('جديد')) == _('جديد'):
                vals['meter_number'] = self.env['ir.sequence'].next_by_code('utility.meter') or _('جديد')
        return super().create(vals_list)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('meter_number', operator, name), ('serial_number', operator, name)]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)

    def name_get(self):
        result = []
        for meter in self:
            name = '[%s]' % meter.meter_number
            if meter.customer_id and meter.customer_id.partner_id:
                name += ' - %s' % meter.customer_id.partner_id.name
            elif meter.transformer_id:
                name += ' - %s' % meter.transformer_id.name
            elif meter.feeder_id:
                name += ' - %s' % meter.feeder_id.name
            result.append((meter.id, name))
        return result


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

    name = fields.Char('اسم الموديل', required=True)
    code = fields.Char('رمز الموديل', required=True)
    manufacturer = fields.Char('الشركة المصنّعة')
    meter_type_id = fields.Many2one('utility.meter.type', 'نوع العداد')
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور')
    voltage_range = fields.Char('نطاق الجهد')
    current_range = fields.Char('نطاق شدة التيار')
    sts_supported = fields.Boolean('يدعم STS')
    communication_types = fields.Char('أنواع الاتصال')
    description = fields.Text('الوصف')
    product_id = fields.Many2one(
        'product.product', 'المنتج',
        help="المنتج الذي يمثل هذا الموديل في نظام المخزون والمحاسبة",
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
