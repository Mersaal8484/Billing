import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UtilityCustomer(models.Model):
    _name = 'utility.customer'
    _description = 'Utility Customer & Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'customer_number'
    _rec_name = 'customer_number'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', 'Partner', required=True)
    customer_number = fields.Char('Customer Number', required=True, index=True, default=lambda self: _('New'))
    account_number = fields.Char('Account Number', related='customer_number', store=True, readonly=True)
    national_id = fields.Char('National ID', index=True)
    mobile = fields.Char('Mobile')
    phone = fields.Char('Phone')
    
    # حالة الاشتراك/العميل الأساسية
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('disconnected', 'Disconnected'),
        ('closed', 'Closed'),
    ], string='State', default='draft', tracking=True)

    connection_status = fields.Selection([
        ('active', 'Active'),
        ('disconnected', 'Disconnected'),
        ('suspended', 'Suspended'),
        ('pending', 'Pending'),
    ], string='Connection Status', compute='_compute_connection_status', store=True)

    area_id = fields.Many2one('utility.region', 'Area', index=True, domain="[('type', '=', 'area')]")
    zone_id = fields.Many2one('utility.region', 'Zone', domain="[('type', '=', 'zone')]")
    region_id = fields.Many2one('utility.region', 'Region', index=True, related='area_id.parent_id', store=True)
    office_id = fields.Many2one('utility.office', 'Office')
    gps_latitude = fields.Float('GPS Latitude')
    gps_longitude = fields.Float('GPS Longitude')

    # حقول العقد والعداد والتعرفة المدمجة
    meter_id = fields.Many2one('utility.meter', 'Meter')
    tariff_id = fields.Many2one('utility.tariff', 'Tariff', compute='_compute_tariff_id', store=True, readonly=False)
    balance = fields.Monetary('Balance', currency_field='company_currency_id')
    emergency_credit = fields.Monetary('Emergency Credit', currency_field='company_currency_id')
    total_purchases = fields.Monetary('Total Purchases', currency_field='company_currency_id')
    total_kwh_purchased = fields.Float('Total kWh Purchased')
    last_purchase_date = fields.Datetime('Last Purchase Date')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Currency')

    # حقول تفاصيل العقد
    contract_template_id = fields.Many2one('utility.contract.template', string='نموذج العقد')
    date_contract = fields.Date(string='تاريخ العقد')
    date_sub_start = fields.Date(string='تاريخ بداية الاشتراك')
    date_end = fields.Date(string='تاريخ انتهاء العقد')
    recurring_next_date = fields.Date(string='تاريخ الفاتورة القادمة')
    contract_state = fields.Selection([
        ('new', 'جديد'),
        ('active', 'نشط'),
        ('suspended', 'موقوف'),
        ('closed', 'مغلق'),
    ], string='حالة العقد', compute='_compute_contract_state', store=True)

    last_reading_date = fields.Datetime()
    last_invoice_date = fields.Datetime()
    last_reading_value = fields.Float('آخر قراءة مسجلة')
    last_invoice_reading = fields.Float('آخر قراءة مفوترة')

    # حقول خلايا المحولات
    cell_id = fields.Many2one('utility.transformer', 'المحول', index=True)
    coupling_meter_id = fields.Many2one('utility.meter', related='cell_id.coupling_meter_id', store=True, string='عداد الربط')
    is_private_transformer = fields.Boolean('محول خاص', related='cell_id.is_private', store=True)
    distribution_percentage = fields.Float('نسبة التوزيع %', related='cell_id.distribution_percentage', store=True)

    route_id = fields.Many2one('utility.route', 'المسار', index=True)

    # الحساب التحليلي
    analytic_account_id = fields.Many2one('account.analytic.account', string='الحساب التحليلي', index=True)

    subscriber_category_id = fields.Many2one('utility.subscriber.category',
        string='فئة المشترك', index=True,
        domain="[('level', '=', 'subcategory')]")

    meter_count = fields.Integer('Meter Count', compute='_compute_meter_count', store=True)
    invoice_count = fields.Integer(compute='_compute_smart_buttons', string='عدد الفواتير')
    reading_count = fields.Integer(compute='_compute_smart_buttons', string='عدد القراءات')
    payment_count = fields.Integer(compute='_compute_smart_buttons', string='عدد الدفعات')

    _sql_constraints = [
        ('unique_customer_number_company', 'unique(customer_number, company_id)',
         'Customer/Account number must be unique per company!'),
    ]

    @api.depends('contract_template_id')
    def _compute_tariff_id(self):
        for rec in self:
            if rec.contract_template_id:
                rec.tariff_id = rec.contract_template_id.tariff_id
            elif not rec.tariff_id:
                rec.tariff_id = False

    @api.depends('state')
    def _compute_contract_state(self):
        for rec in self:
            if rec.state == 'draft':
                rec.contract_state = 'new'
            elif rec.state == 'active':
                rec.contract_state = 'active'
            elif rec.state == 'suspended' or rec.state == 'disconnected':
                rec.contract_state = 'suspended'
            else:
                rec.contract_state = 'closed'

    @api.depends('state')
    def _compute_connection_status(self):
        for rec in self:
            if rec.state == 'active':
                rec.connection_status = 'active'
            elif rec.state == 'suspended':
                rec.connection_status = 'suspended'
            elif rec.state == 'disconnected':
                rec.connection_status = 'disconnected'
            else:
                rec.connection_status = 'pending'

    @api.depends('meter_id')
    def _compute_meter_count(self):
        for r in self:
            r.meter_count = 1 if r.meter_id else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('customer_number', _('New')) == _('New'):
                vals['customer_number'] = self.env['ir.sequence'].next_by_code('utility.customer') or _('New')
        records = super().create(vals_list)
        for record in records:
            record.action_create_analytic_account()
        return records

    def name_get(self):
        res = []
        for rec in self:
            name = f"{rec.customer_number} - {rec.partner_id.name}"
            res.append((rec.id, name))
        return res

    def action_create_analytic_account(self):
        Analytic = self.env['account.analytic.account']
        for rec in self:
            if not rec.analytic_account_id:
                name = f"كهرباء - {rec.customer_number} - {rec.partner_id.name}"
                analytic = Analytic.create({
                    'name': name,
                    'utility_customer_id': rec.id,
                })
                rec.analytic_account_id = analytic.id

    @api.model
    def cron_check_low_credit(self):
        threshold = float(self.env['ir.config_parameter'].sudo().get_param('utility.low_credit_threshold', 100.0))
        accounts = self.search([
            ('contract_state', '=', 'active'),
            ('balance', '<', threshold),
        ])
        for account in accounts:
            _logger.info("Customer/Account %s has low credit balance: %s", account.customer_number, account.balance)

    @api.model
    def cron_retry_auto_pay(self):
        _logger.info("Retrying auto pay for active accounts...")

    def _compute_smart_buttons(self):
        Bill = self.env['utility.bill']
        Reading = self.env['utility.reading']
        Payment = self.env['utility.collection']
        for rec in self:
            rec.invoice_count = Bill.search_count([('customer_id', '=', rec.id)])
            rec.reading_count = Reading.search_count([('customer_id', '=', rec.id)])
            rec.payment_count = Payment.search_count([('customer_id', '=', rec.id)])

    def action_view_bills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bills'),
            'res_model': 'utility.bill',
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
            'res_model': 'utility.collection',
            'domain': [('customer_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }
