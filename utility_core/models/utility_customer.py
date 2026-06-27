from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class UtilityCustomer(models.Model):
    _name = 'utility.customer'
    _description = 'مشترك كهرباء / حساب كهرباء'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'customer_number'
    _order = 'customer_number asc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    customer_number = fields.Char('Customer Number', required=True, index=True, default=lambda self: _('New'))
    partner_id = fields.Many2one('res.partner', 'العميل (شخص)', required=True, domain=[('is_company', '=', False)])
    account_type = fields.Selection([
        ('residential', 'سكني'),
        ('commercial', 'تجاري'),
        ('industrial', 'صناعي'),
        ('agricultural', 'زراعي'),
        ('government', 'حكومي'),
    ], string='نوع الحساب', default='residential')
    phone = fields.Char(related='partner_id.phone', string='رقم الجوال')
    email = fields.Char(related='partner_id.email', string='البريد الإلكتروني')
    subscriber_category_id = fields.Many2one('utility.subscriber.category', string='فئة المشترك')

    # العقود
    contract_state = fields.Selection([
        ('active', 'نشط'),
        ('suspended', 'موقوف'),
        ('disconnected', 'مفصول'),
        ('closed', 'مغلق'),
    ], string='حالة الاشتراك', default='active', tracking=True,
        help='حالة الاشتراك الحالية للمشترك')
    contract_template_id = fields.Many2one('utility.contract.template',
        string='نموذج العقد',
        domain="[('subscriber_category_ids', '=', subscriber_category_id)]")
    contract_start_date = fields.Date('تاريخ بداية العقد')
    contract_end_date = fields.Date('تاريخ نهاية العقد')

    # التعرفة
    tariff_id = fields.Many2one('utility.tariff', 'التعرفة', domain="[('category_ids', '=', subscriber_category_id)]")
    tariff_segment_id = fields.Many2one(related='tariff_id.segment_id', string='شريحة التعرفة')

    # المحول (Cell)
    cell_id = fields.Many2one('utility.transformer', string='المحول/الخلية',
        domain="[('is_cell', '=', True), ('active', '=', True)]")

    # عداد المحول (لربط قراءات الربط)
    cell_coupling_meter_id = fields.Many2one('utility.meter', 'عداد الخلية',
        domain="[('transformer_id', '=', cell_id)]")

    # المكان
    region_id = fields.Many2one(related='partner_id.region_id', store=True, string='المنطقة')
    area_id = fields.Many2one(related='partner_id.area_id', store=True, string='المنطقة الفرعية')
    zone_id = fields.Many2one(related='partner_id.zone_id', store=True, string='المنطقة التفصيلية')

    # العداد
    meter_id = fields.Many2one('utility.meter', 'العداد', tracking=True)

    # الرصيد
    balance = fields.Float('الرصيد', default=0.0, help='الرصيد الحالي للمشترك')
    emergency_credit = fields.Float('رصيد الطوارئ', default=0.0)
    credit_limit = fields.Float('حد الائتمان', default=0.0)

    # آخر قراءة
    last_reading_date = fields.Datetime('آخر تاريخ قراءة')
    last_reading_value = fields.Float('آخر قراءة')
    last_invoice_date = fields.Datetime('آخر تاريخ فاتورة')
    last_invoice_reading = fields.Float('قراءة آخر فاتورة')

    # الشرائح المحسوبة للفوترة
    tariff_block_ids = fields.One2many('utility.tariff.block', compute='_compute_tariff_blocks',
        string='شرائح التعرفة')

    # قراءات الربط
    coupling_reading_ids = fields.One2many('utility.transformer.reading', 'customer_id',
        string='قراءات الربط', domain=[('reading_type', '=', 'coupling')])
    cell_reading_ids = fields.One2many('utility.transformer.reading', 'customer_id',
        string='قراءات الخلية', domain=[('reading_type', '=', 'cell')])

    # الأزرار الذكية
    invoice_count = fields.Integer('عدد الفواتير', compute='_compute_smart_buttons')
    reading_count = fields.Integer('عدد القراءات', compute='_compute_smart_buttons')
    payment_count = fields.Integer('عدد الدفعات', compute='_compute_smart_buttons')

    _sql_constraints = [
        ('unique_customer_number_company', 'unique(customer_number, company_id)',
         'Customer number must be unique per company!'),
    ]

    @api.depends('tariff_id', 'tariff_id.block_ids', 'tariff_id.block_ids.block_sequence')
    def _compute_tariff_blocks(self):
        for rec in self:
            if rec.tariff_id:
                rec.tariff_block_ids = rec.tariff_id.block_ids.sorted('block_sequence')
            else:
                rec.tariff_block_ids = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('customer_number', _('New')) == _('New'):
                vals['customer_number'] = self.env['ir.sequence'].next_by_code('utility.customer') or _('New')
        return super().create(vals_list)

    @api.constrains('cell_id', 'meter_id')
    def _check_cell_meter_consistency(self):
        for rec in self:
            if rec.cell_id and rec.meter_id:
                cell = rec.cell_id
                cell_meters = cell.meter_ids | cell.coupling_meter_ids
                if rec.meter_id not in cell_meters:
                    raise ValidationError(
                        f"العداد {rec.meter_id.meter_number} لا يتبع المحول/الخلية {cell.name}! "
                        "يرجى اختيار عداد مرتبط بهذا المحول."
                    )

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, f'[{rec.customer_number}] {rec.partner_id.name}'))
        return res

    @api.model
    def cron_check_low_credit(self):
        accounts = self.search([
            ('active', '=', True),
            ('balance', '<=', 'credit_limit'),
        ])
        for account in accounts:
            _logger.info("Customer/Account %s has low credit balance: %s", account.customer_number, account.balance)

    @api.model
    def cron_retry_auto_pay(self):
        _logger.info("Retrying auto pay for active accounts...")

    def _compute_smart_buttons(self):
        SaleOrder = self.env.get('sale.order')
        Reading = self.env.get('utility.reading')
        for rec in self:
            rec.invoice_count = SaleOrder.search_count([('customer_id', '=', rec.id)]) if SaleOrder else 0
            rec.reading_count = Reading.search_count([('customer_id', '=', rec.id)]) if Reading else 0
            rec.payment_count = 0

    def action_view_bills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bills'),
            'res_model': 'sale.order',
            'domain': [('customer_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_readings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Readings'),
            'res_model': 'utility.reading',
            'domain': [('customer_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payments'),
            'res_model': 'account.payment',
            'domain': [('utility_sale_order_id.customer_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }
