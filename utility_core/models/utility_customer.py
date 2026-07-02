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
    account_number = fields.Char(related='customer_number', string='Account Number', store=True)
    customer_id = fields.Many2one('utility.customer', compute='_compute_self_customer', string='Customer')
    partner_id = fields.Many2one('res.partner', 'العميل (شخص)', required=True, domain=[('is_company', '=', False)])

    def _compute_self_customer(self):
        for rec in self:
            rec.customer_id = rec.id
    category_id = fields.Many2one('utility.subscriber.category', string='الفئة (نوع الحساب)')
    phone = fields.Char(related='partner_id.phone', string='رقم الجوال')
    mobile = fields.Char(related='partner_id.mobile', string='الجوال')
    email = fields.Char(related='partner_id.email', string='البريد الإلكتروني')
    national_id = fields.Char(string='الهوية الوطنية')
    subscriber_id = fields.Many2one('utility.subscriber', string='نوع المشترك')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('active', 'فعال'),
        ('suspended', 'موقوف'),
        ('disconnected', 'مفصول'),
        ('closed', 'مغلق'),
    ], string='الحالة', default='draft', tracking=True)

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
        domain="[('subscriber_ids', '=', subscriber_id)]")
    contract_start_date = fields.Date('تاريخ بداية العقد')
    contract_end_date = fields.Date('تاريخ نهاية العقد')
    date_contract = fields.Date(string='تاريخ العقد')
    date_sub_start = fields.Date(string='بداية الاشتراك')
    date_end = fields.Date(string='نهاية الاشتراك')
    recurring_next_date = fields.Date(string='تاريخ التكرار القادم')

    analytic_account_id = fields.Many2one('account.analytic.account', string='الحساب التحليلي')
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='العملة')

    # الفيدر / الخلية
    cell_id = fields.Many2one('utility.feeder', string='الفيدر / الخلية',
        domain="[('active', '=', True)]")
    
    # المحول
    transformer_id = fields.Many2one('utility.transformer', string='المحول',
        domain="[('active', '=', True)]")
    is_private_transformer = fields.Boolean(related='transformer_id.is_private', readonly=True, string='هل المحول خاص؟')

    # عداد الفيدر
    cell_coupling_meter_id = fields.Many2one('utility.meter', 'عداد الفيدر/الخلية',
        domain="[('feeder_id', '=', cell_id)]")

    # المكان
    region_id = fields.Many2one(related='partner_id.region_id', store=True, string='المنطقة')
    area_id = fields.Many2one(related='partner_id.area_id', store=True, string='المنطقة الفرعية')
    zone_id = fields.Many2one(related='partner_id.zone_id', store=True, string='المنطقة التفصيلية')

    route_id = fields.Many2one('utility.route', string='خط السير', index=True)

    # العداد
    meter_id = fields.Many2one('utility.meter', 'العداد', tracking=True, required=True)
    payment_type = fields.Selection(related='meter_id.payment_type', store=True, string='نظام الدفع (آجل/مسبق)', readonly=True)

    # الرصيد والمشتريات
    balance = fields.Float('الرصيد', default=0.0, help='الرصيد الحالي للمشترك')
    emergency_credit = fields.Float('رصيد الطوارئ', default=0.0)
    credit_limit = fields.Float('حد الائتمان', default=0.0)
    total_purchases = fields.Float(string='إجمالي المشتريات')
    total_kwh_purchased = fields.Float(string='إجمالي الكيلووات المشترى')
    last_purchase_date = fields.Date(string='تاريخ آخر شراء')

    # آخر قراءة
    last_reading_date = fields.Datetime('آخر تاريخ قراءة')
    last_reading_value = fields.Float('آخر قراءة')
    last_invoice_date = fields.Datetime('آخر تاريخ فاتورة')
    last_invoice_reading = fields.Float('قراءة آخر فاتورة')



    # قراءات الربط
    coupling_reading_ids = fields.One2many('utility.reading', 'account_id',
        string='قراءات الربط', domain=[('reading_category', 'in', ['transformer', 'feeder'])])
    cell_reading_ids = fields.One2many('utility.reading', 'account_id',
        string='قراءات الخلية', domain=[('reading_category', '=', 'transformer')])
    uploaded_reading_ids = fields.One2many('utility.reading', 'account_id',
        domain=[('state', 'in', ['draft', 'under_review', 'approved'])], string='Uploaded Readings')
    billed_reading_ids = fields.One2many('utility.reading', 'account_id',
        domain=[('state', '=', 'billed')], string='Billed Readings')

    # الأزرار الذكية
    invoice_count = fields.Integer('عدد الفواتير', compute='_compute_smart_buttons')
    reading_count = fields.Integer('عدد القراءات', compute='_compute_smart_buttons')
    payment_count = fields.Integer('عدد الدفعات', compute='_compute_smart_buttons')

    _sql_constraints = [
        ('unique_customer_number_company', 'unique(customer_number, company_id)',
         'Customer number must be unique per company!'),
    ]



    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('customer_number', _('New')) == _('New'):
                vals['customer_number'] = self.env['ir.sequence'].next_by_code('utility.customer') or _('New')
        
        customers = super().create(vals_list)
        
        for customer in customers:
            # تعيين المشترك كعميل في قائمة العملاء (res.partner)
            if customer.partner_id:
                customer.partner_id.sudo().write({
                    'customer_rank': max(customer.partner_id.customer_rank, 1),
                    'is_subscriber': True,
                })

            # Create analytic accounts automatically for each customer
            if not customer.analytic_account_id:
                partner_name = customer.partner_id.name or customer.customer_number
                plan = self.env.ref('analytic.analytic_plan_projects', raise_if_not_found=False)
                if not plan:
                    plan = self.env['account.analytic.plan'].search([], limit=1)
                if not plan:
                    plan = self.env['account.analytic.plan'].create({'name': 'Default Plan'})
                
                analytic_account = self.env['account.analytic.account'].create({
                    'name': f"{partner_name} - {customer.customer_number}",
                    'partner_id': customer.partner_id.id,
                    'plan_id': plan.id
                })
                customer.write({'analytic_account_id': analytic_account.id})
                
        return customers

    def write(self, vals):
        res = super().write(vals)
        # إذا تغيّر الـ partner_id، تعيينه كعميل تلقائياً
        if 'partner_id' in vals:
            for customer in self:
                if customer.partner_id:
                    customer.partner_id.sudo().write({
                        'customer_rank': max(customer.partner_id.customer_rank, 1),
                        'is_subscriber': True,
                    })
        return res

    def _update_balance(self, amount):
        """Apply a prepaid balance delta and keep basic purchase totals aligned."""
        for customer in self:
            delta = amount or 0.0
            customer.balance = (customer.balance or 0.0) + delta
            if delta > 0:
                customer.total_purchases = (customer.total_purchases or 0.0) + delta
                customer.last_purchase_date = fields.Date.context_today(customer)

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



    @api.onchange('subscriber_id')
    def _onchange_subscriber_id(self):
        if self.subscriber_id:
            # التنسيق مع قالب العقد
            if not self.contract_template_id or (self.contract_template_id.subscriber_ids and self.subscriber_id not in self.contract_template_id.subscriber_ids):
                matching_template = self.env['utility.contract.template'].search([('subscriber_ids', 'in', self.subscriber_id.id)], limit=1)
                if not matching_template:
                    matching_template = self.subscriber_id.default_contract_template_id
                self.contract_template_id = matching_template

    @api.constrains('contract_template_id', 'subscriber_id')
    def _check_contract_subscriber_compatibility(self):
        strict_compatibility = self.env['ir.config_parameter'].sudo().get_param('utility.strict_contract_tariff_compatibility', 'False') == 'True'
        
        for rec in self:
            if not strict_compatibility:
                continue
                
            template = rec.contract_template_id
            if template:
                if template.subscriber_ids and rec.subscriber_id and rec.subscriber_id not in template.subscriber_ids:
                    raise ValidationError(
                        f"آلية التناغم الصارمة: قالب العقد '{template.name}' لا يدعم المشترك من نوع '{rec.subscriber_id.name}'. "
                        f"يرجى اختيار قالب عقد متوافق."
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
        ])
        low_credit_accounts = accounts.filtered(lambda a: a.balance <= a.credit_limit)
        for account in low_credit_accounts:
            _logger.info("Customer/Account %s has low credit balance: %s", account.customer_number, account.balance)

    @api.model
    def cron_retry_auto_pay(self):
        _logger.info("Retrying auto pay for active accounts...")

    def _compute_smart_buttons(self):
        SaleOrder = self.env.get('sale.order')
        Reading = self.env.get('utility.reading')
        Payment = self.env.get('account.payment')
        for rec in self:
            rec.invoice_count = SaleOrder.search_count([('customer_id', '=', rec.id)]) if SaleOrder else 0
            rec.reading_count = Reading.search_count([('customer_id', '=', rec.id)]) if Reading else 0
            rec.payment_count = Payment.search_count([('utility_sale_order_id.customer_id', '=', rec.id)]) if Payment else 0

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

    def action_create_analytic_account(self):
        for rec in self:
            if not rec.analytic_account_id:
                plan = self.env.ref('analytic.analytic_plan_projects', raise_if_not_found=False)
                if not plan:
                    plan = self.env['account.analytic.plan'].search([], limit=1)
                if not plan:
                    plan = self.env['account.analytic.plan'].create({'name': 'Default Plan'})

                analytic = self.env['account.analytic.account'].create({
                    'name': f'[{rec.customer_number}] {rec.partner_id.name}',
                    'partner_id': rec.partner_id.id,
                    'company_id': rec.company_id.id,
                    'utility_customer_id': rec.id,
                    'plan_id': plan.id,
                })
                rec.analytic_account_id = analytic.id
