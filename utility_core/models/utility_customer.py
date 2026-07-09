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

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    customer_number = fields.Char('رقم العميل', required=True, index=True, default=lambda self: _('جديد'))
    account_number = fields.Char(related='customer_number', string='رقم الحساب', store=True)
    customer_id = fields.Many2one('utility.customer', compute='_compute_self_customer', string='العميل')
    partner_id = fields.Many2one('res.partner', 'العميل (شخص)', required=True, domain=[('is_company', '=', False)])

    def _compute_self_customer(self):
        for rec in self:
            rec.customer_id = rec.id
    category_id = fields.Many2one('utility.subscriber.category', string='فئة المشترك الرئيسية', required=True)
    phone = fields.Char(related='partner_id.phone', string='رقم الجوال')
    mobile = fields.Char(related='partner_id.mobile', string='الجوال')
    email = fields.Char(related='partner_id.email', string='البريد الإلكتروني')
    national_id = fields.Char(string='الهوية الوطنية')
    subscriber_id = fields.Many2one('utility.subscriber', string='نوع المشترك', required=True, domain="[('category_id', '=', category_id)]")
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
        domain="["
               "('subscriber_category_ids', 'in', [category_id]), "
               "('subscriber_ids', 'in', [subscriber_id]), "
               "'|', ('scope', '=', 'global'), "
               "'|', ('region_ids', 'in', [region_id]), "
               "('area_ids', 'in', [area_id])"
               "]")
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
    balance = fields.Monetary('الرصيد', compute='_compute_balance', currency_field='company_currency_id', help='الرصيد الحالي للمشترك')
    emergency_credit = fields.Monetary('رصيد الطوارئ', default=0.0, currency_field='company_currency_id')
    credit_limit = fields.Monetary('حد الائتمان', default=0.0, currency_field='company_currency_id')
    total_purchases = fields.Monetary(string='إجمالي المشتريات', currency_field='company_currency_id')
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
        domain=[('state', 'in', ['draft', 'under_review', 'approved'])], string='القراءات المرفوعة')
    billed_reading_ids = fields.One2many('utility.reading', 'account_id',
        domain=[('state', '=', 'billed')], string='القراءات المفوتورة')

    # الأزرار الذكية
    invoice_count = fields.Integer('عدد الفواتير', compute='_compute_smart_buttons')
    accounting_invoice_count = fields.Integer('عدد الفواتير المحاسبية', compute='_compute_smart_buttons')
    reading_count = fields.Integer('عدد القراءات', compute='_compute_smart_buttons')
    payment_count = fields.Integer('عدد الدفعات', compute='_compute_smart_buttons')

    _sql_constraints = [
        ('unique_customer_number_company', 'unique(customer_number, company_id)',
         'رقم العميل يجب أن يكون فريداً لكل شركة!'),
    ]



    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('customer_number', _('جديد')) == _('جديد'):
                vals['customer_number'] = self.env['ir.sequence'].next_by_code('utility.customer') or _('جديد')

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

    def _get_contract_template_domain(self):
        self.ensure_one()
        domain = []
        if self.category_id:
            domain.append(('subscriber_category_ids', 'in', [self.category_id.id]))
        if self.subscriber_id:
            domain.append(('subscriber_ids', 'in', [self.subscriber_id.id]))
        location_domain = [('scope', '=', 'global')]
        if self.region_id:
            location_domain = ['|'] + location_domain + [('region_ids', 'in', [self.region_id.id])]
        if self.area_id:
            location_domain = ['|'] + location_domain + [('area_ids', 'in', [self.area_id.id])]
        return domain + location_domain

    def _find_matching_contract_template(self):
        self.ensure_one()
        ContractTemplate = self.env['utility.contract.template']
        if self.subscriber_id and self.subscriber_id.default_contract_template_id:
            default_template = self.subscriber_id.default_contract_template_id
            if ContractTemplate.search_count([('id', '=', default_template.id)] + self._get_contract_template_domain()):
                return default_template
        return ContractTemplate.search(self._get_contract_template_domain(), limit=1)

    @api.onchange('category_id', 'subscriber_id', 'region_id', 'area_id')
    def _onchange_contract_template_domain(self):
        for rec in self:
            domain = rec._get_contract_template_domain()
            if rec.contract_template_id and not self.env['utility.contract.template'].search_count([('id', '=', rec.contract_template_id.id)] + domain):
                rec.contract_template_id = False
            if not rec.contract_template_id and rec.subscriber_id:
                rec.contract_template_id = rec._find_matching_contract_template()
            return {'domain': {'contract_template_id': domain}}

    @api.constrains('category_id', 'subscriber_id')
    def _check_subscriber_category_compatibility(self):
        for rec in self:
            if rec.category_id and rec.subscriber_id:
                if rec.subscriber_id.category_id != rec.category_id:
                    raise ValidationError(
                        _("نوع المشترك '%s' يجب أن ينتمي إلى فئة المشترك الرئيسية المحددة '%s'.")
                        % (rec.subscriber_id.name, rec.category_id.name)
                    )

    @api.constrains('contract_template_id', 'category_id', 'subscriber_id', 'region_id', 'area_id')
    def _check_contract_subscriber_compatibility(self):
        for rec in self:
            template = rec.contract_template_id
            subscriber = rec.subscriber_id
            category = rec.category_id
            if template:
                if category and category not in template.subscriber_category_ids:
                    raise ValidationError(
                        _("قالب العقد '%s' لا يدعم فئة المشترك الرئيسية '%s'.")
                        % (template.name, category.name)
                    )
                if subscriber and subscriber not in template.subscriber_ids:
                    raise ValidationError(
                        _("قالب العقد '%s' لا يدعم نوع المشترك '%s'.")
                        % (template.name, subscriber.name)
                    )
                if template.scope == 'restricted':
                    allowed_region_ids = template.region_ids.ids
                    allowed_area_ids = template.area_ids.ids

                    customer_region_id = rec.region_id.id
                    customer_area_id = rec.area_id.id

                    is_region_allowed = customer_region_id in allowed_region_ids if customer_region_id else False
                    is_area_allowed = customer_area_id in allowed_area_ids if customer_area_id else False

                    if not (is_region_allowed or is_area_allowed):
                        raise ValidationError(
                            _("قالب العقد المختار '%s' مخصص لمناطق محددة ولا يدعم المنطقة أو المنطقة الفرعية لهذا المشترك.")
                            % template.name
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

    def _compute_balance(self):
        Move = self.env.get('account.move')
        for rec in self:
            if Move:
                posted_moves = Move.search([
                    ('partner_id', '=', rec.partner_id.id),
                    ('state', '=', 'posted'),
                    ('move_type', 'in', ('out_invoice', 'out_refund')),
                ])
                rec.balance = sum(posted_moves.mapped('amount_residual_signed'))
            else:
                rec.balance = 0.0

    def _compute_smart_buttons(self):
        SaleOrder = self.env.get('sale.order')
        Reading = self.env.get('utility.reading')
        Payment = self.env.get('account.payment')
        Move = self.env.get('account.move')
        for rec in self:
            rec.invoice_count = SaleOrder.search_count([('customer_id', '=', rec.id)]) if SaleOrder else 0
            rec.accounting_invoice_count = Move.search_count([
                ('partner_id', '=', rec.partner_id.id),
                ('state', '=', 'posted'),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
            ]) if Move else 0
            rec.reading_count = Reading.search_count([('customer_id', '=', rec.id)]) if Reading else 0
            rec.payment_count = Payment.search_count([('utility_sale_order_id.customer_id', '=', rec.id)]) if Payment else 0

    def action_view_bills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('الفواتير'),
            'res_model': 'sale.order',
            'domain': [('customer_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_accounting_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('الفواتير المحاسبية'),
            'res_model': 'account.move',
            'domain': [
                ('partner_id', '=', self.partner_id.id),
                ('state', '=', 'posted'),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
            ],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_readings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('القراءات'),
            'res_model': 'utility.reading',
            'domain': [('customer_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('الدفعات'),
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
