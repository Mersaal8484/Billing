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

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    meter_number = fields.Char('Meter Number', required=True, index=True, default=lambda self: _('New'))
    serial_number = fields.Char('Serial Number', index=True)
    manufacturer = fields.Char('Manufacturer')
    model_id = fields.Many2one('utility.meter.model', 'Model')
    payment_type = fields.Selection([
        ('postpaid', 'آجل الدفع (عن بُعد / ذكي)'),
        ('prepaid', 'دفع مسبق (Prepaid)'),
        ('manual', 'يدوي (Manual)')
    ], string='نظام العداد', default='manual', required=True)
    meter_type_id = fields.Many2one('utility.meter.type', 'Meter Type')
    status_id = fields.Many2one('utility.meter.status', 'Status')
    phase = fields.Selection([
        ('single', 'Single Phase'),
        ('three', 'Three Phase'),
    ], string='الطور')
    voltage = fields.Float('Voltage (V)')
    current_rating = fields.Float('Current Rating (A)')
    power_rating = fields.Float('Power Rating (kW)')
    sts_key_revision = fields.Char('STS Key Revision')
    customer_id = fields.Many2one('utility.customer', 'Customer/Contract', index=True)
    account_id = fields.Many2one('utility.customer', string='الحساب', related='customer_id', store=True)
    area_id = fields.Many2one('utility.region', 'Area', domain="[('type', '=', 'area')]")
    zone_id = fields.Many2one('utility.region', 'Zone', domain="[('type', '=', 'zone')]")
    region_id = fields.Many2one('utility.region', 'Region', related='area_id.parent_id', store=True)
    route_id = fields.Many2one('utility.route', 'Route', related='customer_id.route_id', store=True)
    feeder_id = fields.Many2one('utility.feeder', 'Feeder')
    transformer_id = fields.Many2one('utility.transformer', 'Transformer')
    substation_id = fields.Many2one('utility.substation', 'Substation')
    installation_date = fields.Date('Installation Date')
    address = fields.Text('Address')
    communication_type = fields.Selection([
        ('gsm', 'GSM'),
        ('nbiot', 'NB-IoT'),
        ('lora', 'LoRa'),
        ('rf', 'RF'),
        ('plc', 'PLC'),
        ('manual', 'Manual'),
    ], string='نوع الاتصال')
    sim_number = fields.Char('SIM Number')
    last_read_date = fields.Datetime('Last Read Date')
    qr_code_value = fields.Char('بيانات QR', compute='_compute_qr_code', readonly=True)
    qr_code_url = fields.Char('رابط QR', compute='_compute_qr_code', readonly=True)


    # خصائص الربط
    is_coupling_meter = fields.Boolean('عداد ربط رئيسي', default=False, help='يُشير إذا كان هذا العداد هو عداد ربط يقرأ إجمالي طاقة الفيدر أو المحطة')

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
         'Meter number must be unique per company!'),
        ('unique_serial_number', 'unique(serial_number)', 'Serial number must be unique!'),
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
            if vals.get('meter_number', _('New')) == _('New'):
                vals['meter_number'] = self.env['ir.sequence'].next_by_code('utility.meter') or _('New')
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

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    phase = fields.Selection([
        ('single', 'Single Phase'),
        ('three', 'Three Phase'),
    ], string='الطور')
    description = fields.Text('Description')


class UtilityMeterModel(models.Model):
    _name = 'utility.meter.model'
    _description = 'موديل العداد'
    _order = 'name'

    name = fields.Char('Model Name', required=True)
    code = fields.Char('Model Code', required=True)
    manufacturer = fields.Char('Manufacturer')
    meter_type_id = fields.Many2one('utility.meter.type', 'Meter Type')
    phase = fields.Selection([
        ('single', 'Single Phase'),
        ('three', 'Three Phase'),
    ], string='الطور')
    voltage_range = fields.Char('Voltage Range')
    current_range = fields.Char('Current Range')
    sts_supported = fields.Boolean('STS Supported')
    communication_types = fields.Char('Communication Types')
    description = fields.Text('Description')
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

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    sequence = fields.Integer('Sequence')
    description = fields.Text('Description')
