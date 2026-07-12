from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class UtilityCustomer(models.Model):
    _name = 'utility.customer'
    _description = 'مشترك كهرباء / حساب كهرباء'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'utility.dropdown.mixin']
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

    contract_state = fields.Selection([
        ('active', 'نشط'),
        ('suspended', 'موقوف'),
        ('disconnected', 'مفصول'),
        ('closed', 'مغلق'),
    ], string='حالة الاشتراك', default='active', tracking=True,
        help='حالة الاشتراك الحالية للمشترك')
    available_contract_template_ids = fields.Many2many('utility.contract.template', compute='_compute_available_contract_template_ids')
    contract_template_id = fields.Many2one('utility.contract.template', string='نموذج العقد')
    contract_start_date = fields.Date('تاريخ بداية العقد')
    contract_end_date = fields.Date('تاريخ نهاية العقد')
    date_contract = fields.Date(string='تاريخ العقد')
    date_sub_start = fields.Date(string='بداية الاشتراك')
    date_end = fields.Date(string='نهاية الاشتراك')
    recurring_next_date = fields.Date(string='تاريخ التكرار القادم')

    analytic_account_id = fields.Many2one('account.analytic.account', string='الحساب التحليلي')
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='العملة')

    cell_id = fields.Many2one('utility.feeder', string='الفيدر / الخلية',
        domain="[('active', '=', True)]")
    transformer_id = fields.Many2one('utility.transformer', string='المحول',
        domain="[('active', '=', True)]")
    is_private_transformer = fields.Boolean(related='transformer_id.is_private', readonly=True, string='هل المحول خاص؟')
    cell_coupling_meter_id = fields.Many2one('utility.meter', 'عداد الفيدر/الخلية',
        domain="[('feeder_id', '=', cell_id)]")

    region_id = fields.Many2one(related='partner_id.region_id', store=True, string='المنطقة')
    area_id = fields.Many2one(related='partner_id.area_id', store=True, string='المنطقة الفرعية')
    zone_id = fields.Many2one(related='partner_id.zone_id', store=True, string='المنطقة التفصيلية')

    route_id = fields.Many2one('utility.route', string='خط السير', index=True)

    meter_id = fields.Many2one('utility.meter', 'العداد', tracking=True)
    payment_type = fields.Selection(related='meter_id.payment_type', store=True, string='نظام الدفع (آجل/مسبق)', readonly=True)

    # الرصيد المحاسبي (آجل) — من move lines محاسبية
    accounting_balance = fields.Monetary(
        'الرصيد المحاسبي', compute='_compute_accounting_balance',
        currency_field='company_currency_id',
        help='الرصيد المستحق بناءً على القيود المحاسبية (الذمم المدينة)')

    # رصيد مسبق الدفع (محفظة المشترك)
    prepaid_balance = fields.Monetary(
        'الرصيد المسبق', compute='_compute_prepaid_balance',
        currency_field='company_currency_id',
        help='رصيد المشترك النقدي المسبق الدفع')

    emergency_credit = fields.Monetary('رصيد الطوارئ', default=0.0, currency_field='company_currency_id')
    previous_hotline_balance = fields.Char(related='partner_id.previous_hotline_balance', string='الرصيد السابق (الخط الساخن)', readonly=True)
    credit_limit = fields.Monetary('حد الائتمان', default=0.0, currency_field='company_currency_id')
    total_purchases = fields.Monetary(string='إجمالي المشتريات', currency_field='company_currency_id')
    total_kwh_purchased = fields.Float(string='إجمالي الكيلووات المشترى')
    last_purchase_date = fields.Date(string='تاريخ آخر شراء')

    last_reading_date = fields.Datetime('آخر تاريخ قراءة')
    last_reading_value = fields.Float('آخر قراءة')
    last_invoice_date = fields.Datetime('آخر تاريخ فاتورة')
    last_invoice_reading = fields.Float('قراءة آخر فاتورة')

    # معاملات المحفظة (للرصيد المسبق)
    balance_transaction_ids = fields.One2many(
        'utility.customer.balance.transaction', 'customer_id',
        string='حركات رصيد المحفظة')
    balance_transaction_count = fields.Integer(
        'عدد حركات الرصيد', compute='_compute_balance_transaction_count')

    @api.depends('balance_transaction_ids')
    def _compute_balance_transaction_count(self):
        for rec in self:
            rec.balance_transaction_count = len(rec.balance_transaction_ids)

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
    replacement_count = fields.Integer('استبدالات العداد', compute='_compute_smart_buttons')
    tamper_count = fields.Integer('حالات التلاعب', compute='_compute_smart_buttons')

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
            if customer.partner_id:
                customer.partner_id.sudo().write({
                    'customer_rank': max(customer.partner_id.customer_rank, 1),
                    'is_subscriber': True,
                })
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
        if 'partner_id' in vals:
            for customer in self:
                if customer.partner_id:
                    customer.partner_id.sudo().write({
                        'customer_rank': max(customer.partner_id.customer_rank, 1),
                        'is_subscriber': True,
                    })
        return res

    def _create_balance_transaction(self, ttype, amount, source_ref=None, notes=''):
        """إنشاء حركة رصيد جديدة في محفظة المشترك (يُستبدل _update_balance القديم)."""
        for customer in self:
            balance_before = customer.prepaid_balance
            balance_after = balance_before + amount
            source_model = source_ref._name if source_ref else False
            source_id = source_ref.id if source_ref else False
            txn = self.env['utility.customer.balance.transaction'].create({
                'customer_id': customer.id,
                'transaction_type': ttype,
                'amount': amount,
                'balance_before': balance_before,
                'balance_after': balance_after,
                'source_model': source_model,
                'source_id': source_id,
                'notes': notes,
                'state': 'posted',
            })
            if amount > 0:
                customer.total_purchases = (customer.total_purchases or 0.0) + amount
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

    @api.depends('category_id', 'subscriber_id', 'region_id', 'area_id')
    def _compute_available_contract_template_ids(self):
        for rec in self:
            domain = self._get_contract_template_domain(
                category_id=rec.category_id.id if rec.category_id else False,
                subscriber_id=rec.subscriber_id.id if rec.subscriber_id else False,
                region_id=rec.region_id.id if rec.region_id else False,
                area_id=rec.area_id.id if rec.area_id else False,
            )
            rec.available_contract_template_ids = self.env['utility.contract.template'].search(domain)

    def _find_matching_contract_template(self):
        self.ensure_one()
        if self.subscriber_id and self.subscriber_id.default_contract_template_id:
            default_template = self.subscriber_id.default_contract_template_id
            if default_template in self.available_contract_template_ids:
                return default_template
        if self.available_contract_template_ids:
            return self.available_contract_template_ids[0]
        return self.env['utility.contract.template']

    @api.onchange('category_id', 'subscriber_id', 'region_id', 'area_id')
    def _onchange_contract_template_domain(self):
        available_templates = self.available_contract_template_ids
        if self.contract_template_id and self.contract_template_id not in available_templates:
            self.contract_template_id = False
        if not self.contract_template_id and self.subscriber_id:
            self.contract_template_id = self._find_matching_contract_template()
        return {'domain': {'contract_template_id': [('id', 'in', available_templates.ids)]}}

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
                    customer_region_id = rec.region_id.id if rec.region_id else False
                    customer_area_id = rec.area_id.id if rec.area_id else False
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
        accounts = self.search([('active', '=', True)])
        low_credit_accounts = accounts.filtered(
            lambda a: a.prepaid_balance <= a.credit_limit)
        for account in low_credit_accounts:
            _logger.info("Customer/Account %s has low prepaid balance: %s",
                         account.customer_number, account.prepaid_balance)

    @api.model
    def cron_retry_auto_pay(self):
        _logger.info("Retrying auto pay for active accounts...")

    @api.depends('partner_id')
    def _compute_accounting_balance(self):
        MoveLine = self.env.get('account.move.line')
        if not MoveLine:
            for rec in self:
                rec.accounting_balance = 0.0
            return
        for rec in self:
            if not rec.partner_id:
                rec.accounting_balance = 0.0
                continue
            receivable_accounts = self.env['account.account'].search([
                ('account_type', '=', 'asset_receivable'),
                ('company_id', '=', rec.company_id.id),
            ])
            if not receivable_accounts:
                rec.accounting_balance = 0.0
                continue
            domain = [
                ('partner_id', '=', rec.partner_id.id),
                ('account_id', 'in', receivable_accounts.ids),
                ('parent_state', '=', 'posted'),
                ('reconciled', '=', False),
            ]
            lines = MoveLine.read_group(
                domain,
                ['amount_residual:sum'],
                [],
            )
            rec.accounting_balance = lines[0]['amount_residual'] if lines else 0.0

    @api.depends('balance_transaction_ids', 'balance_transaction_ids.state')
    def _compute_prepaid_balance(self):
        for rec in self:
            posted = rec.balance_transaction_ids.filtered(lambda t: t.state == 'posted')
            rec.prepaid_balance = sum(posted.mapped('amount'))

    def _compute_smart_buttons(self):
        So = self.env.get('sale.order')
        Reading = self.env.get('utility.reading')
        Payment = self.env.get('account.payment')
        Move = self.env.get('account.move')
        Replacement = self.env.get('utility.meter.replacement')
        Tamper = self.env.get('utility.tamper.case')
        for rec in self:
            invoice_count = 0
            accounting_invoice_count = 0
            reading_count = 0
            payment_count = 0
            replacement_count = 0
            tamper_count = 0
            if So and 'customer_id' in So._fields:
                invoice_count = So.sudo().search_count([('customer_id', '=', rec.id)])
            if Reading and 'customer_id' in Reading._fields:
                reading_count = Reading.sudo().search_count([('customer_id', '=', rec.id)])
            if Payment:
                payment_count = Payment.sudo().search_count(
                    [('utility_sale_order_id.customer_id', '=', rec.id)])
            if Move:
                accounting_invoice_count = Move.sudo().search_count([
                    ('partner_id', '=', rec.partner_id.id),
                    ('state', '=', 'posted'),
                    ('move_type', 'in', ('out_invoice', 'out_refund')),
                ])
            if Replacement:
                replacement_count = Replacement.sudo().search_count([('utility_account_id', '=', rec.id)])
            if Tamper:
                tamper_count = Tamper.sudo().search_count([('customer_id', '=', rec.id)])

            rec.invoice_count = invoice_count
            rec.accounting_invoice_count = accounting_invoice_count
            rec.reading_count = reading_count
            rec.payment_count = payment_count
            rec.replacement_count = replacement_count
            rec.tamper_count = tamper_count

    def action_view_balance_transactions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('حركات الرصيد'),
            'res_model': 'utility.customer.balance.transaction',
            'domain': [('customer_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_replacements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('استبدالات العداد'),
            'res_model': 'utility.meter.replacement',
            'domain': [('utility_account_id', '=', self.id)],
            'context': {'default_utility_account_id': self.id},
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_tampers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('حالات التلاعب'),
            'res_model': 'utility.tamper.case',
            'domain': [('customer_id', '=', self.id)],
            'context': {'default_customer_id': self.id},
            'views': [(False, 'tree'), (False, 'form')],
        }

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
