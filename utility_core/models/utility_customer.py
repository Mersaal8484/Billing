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
    owner_partner_id = fields.Many2one(
        'res.partner', 'المالك القانوني', index=True,
        help='الشخص أو الشركة الفعلية المالكة للحساب الكهربائي.')
    partner_id = fields.Many2one(
        'res.partner', 'الشريك المحاسبي', required=True, index=True,
        help='شريك محاسبي مخصص لهذا الحساب الكهربائي فقط.')

    category_id = fields.Many2one('utility.subscriber.category', string='فئة المشترك الرئيسية', required=True)
    mobile = fields.Char(related='partner_id.mobile', string='رقم الجوال', readonly=False, size=9)
    subscriber_id = fields.Many2one('utility.subscriber', string='نوع المشترك', required=True, domain="[('category_id', '=', category_id)]")
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('active', 'فعال'),
        ('suspended', 'موقوف'),
        ('disconnected', 'مفصول'),
        ('closed', 'مغلق'),
    ], string='الحالة', default='draft', tracking=True)

    available_contract_template_ids = fields.Many2many('utility.contract.template', compute='_compute_available_contract_template_ids')
    contract_template_id = fields.Many2one('utility.contract.template', string='نموذج العقد')
    contract_start_date = fields.Date('تاريخ بداية العقد')
    contract_end_date = fields.Date('تاريخ نهاية العقد')
    date_contract = fields.Date(string='تاريخ العقد')
    date_sub_start = fields.Date(string='بداية الاشتراك')
    date_end = fields.Date(string='نهاية الاشتراك')

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

    # ── الحساب التجميعي (كبار المشتركين / الجهات الحكومية) ─────────────────
    is_master_account = fields.Boolean(
        'حساب تجميعي رئيسي',
        help='حدد هذا الخيار إذا كان الحساب يجمع مديونيات وفواتير عدة فروع أو المرافق التابعة (مثل الجهات الحكومية أو الشركات الكبيرة).'
    )
    parent_account_id = fields.Many2one(
        'utility.customer', string='الحساب الرئيسي / التجميعي',
        domain="[('is_master_account', '=', True), ('id', '!=', id)]", index=True,
    )
    child_account_ids = fields.One2many('utility.customer', 'parent_account_id', string='الحسابات التابعة')
    child_account_count = fields.Integer('عدد الحسابات التابعة', compute='_compute_child_account_count')
    aggregate_balance = fields.Monetary(
        'إجمالي مديونية الحسابات التابعة', compute='_compute_aggregate_balance',
        currency_field='company_currency_id',
        help='إجمالي المديونيات المستحقة لجميع الحسابات التابعة للحساب التجميعي.')
    aggregate_overdue_count = fields.Integer(
        'فواتير متأخرة (الحسابات التابعة)', compute='_compute_aggregate_balance',
        help='عدد الفواتير المتأخرة لجميع الحسابات التابعة.')

    @api.depends('child_account_ids')
    def _compute_child_account_count(self):
        for rec in self:
            rec.child_account_count = len(rec.child_account_ids)

    @api.depends('child_account_ids.accounting_balance', 'child_account_ids.invoice_count')
    def _compute_aggregate_balance(self):
        for rec in self:
            if rec.is_master_account and rec.child_account_ids:
                rec.aggregate_balance = sum(child.accounting_balance for child in rec.child_account_ids)
                SaleOrder = self.env.get('sale.order')
                if SaleOrder is not None:
                    rec.aggregate_overdue_count = SaleOrder.sudo().search_count([
                        ('customer_id', 'in', rec.child_account_ids.ids),
                        ('bill_state', '=', 'overdue'),
                    ])
                else:
                    rec.aggregate_overdue_count = 0
            else:
                rec.aggregate_balance = 0.0
                rec.aggregate_overdue_count = 0

    def action_view_child_accounts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('الحسابات التابعة'),
            'res_model': 'utility.customer',
            'domain': [('parent_account_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_child_bills(self):
        """عرض فواتير جميع الحسابات التابعة للحساب التجميعي."""
        self.ensure_one()
        child_ids = self.child_account_ids.ids if self.is_master_account else [self.id]
        return {
            'type': 'ir.actions.act_window',
            'name': _('فواتير الحسابات التابعة'),
            'res_model': 'sale.order',
            'domain': [('customer_id', 'in', child_ids)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_child_overdue_bills(self):
        """عرض الفواتير المتأخرة للحسابات التابعة."""
        self.ensure_one()
        child_ids = self.child_account_ids.ids if self.is_master_account else [self.id]
        return {
            'type': 'ir.actions.act_window',
            'name': _('فواتير متأخرة - الحسابات التابعة'),
            'res_model': 'sale.order',
            'domain': [
                ('customer_id', 'in', child_ids),
                ('bill_state', '=', 'overdue'),
            ],
            'views': [(False, 'tree'), (False, 'form')],
        }

    # الرصيد المحاسبي (آجل) — من move lines محاسبية
    accounting_balance = fields.Monetary(
        'الرصيد المحاسبي', compute='_compute_accounting_balance',
        currency_field='company_currency_id',
        help='الرصيد المستحق بناءً على القيود المحاسبية (الذمم المدينة)')


    opening_balance = fields.Monetary(
        string='الرصيد الافتتاحي',
        currency_field='company_currency_id',
        related='partner_id.open_balance',
        readonly=True,
    )
    opening_move_id = fields.Many2one('account.move', string="قيد الرصيد الافتتاحي", readonly=True)
    current_balance = fields.Monetary(string='المديونية الحالية', currency_field='company_currency_id', related='accounting_balance', store=False)
    
    last_reading_date = fields.Datetime('آخر تاريخ قراءة')
    last_reading_value = fields.Float('آخر قراءة')
    last_invoice_date = fields.Datetime('آخر تاريخ فاتورة')
    last_invoice_reading = fields.Float('قراءة آخر فاتورة')


    uploaded_reading_ids = fields.One2many(
        'utility.reading', 'account_id',
        domain=[('state', 'in', ['draft', 'under_review', 'approved'])],
        string='Uploaded Readings')
    billed_reading_ids = fields.One2many(
        'utility.reading', 'account_id',
        domain=[('state', '=', 'billed')],
        string='Billed Readings')

    invoice_count = fields.Integer('Bills', compute='_compute_smart_buttons')
    accounting_invoice_count = fields.Integer('Accounting Invoices', compute='_compute_smart_buttons')
    reading_count = fields.Integer('Readings', compute='_compute_smart_buttons')
    payment_count = fields.Integer('Payments', compute='_compute_smart_buttons')
    replacement_count = fields.Integer('Meter Replacements', compute='_compute_smart_buttons')
    tamper_count = fields.Integer('Tamper Cases', compute='_compute_smart_buttons')

    _sql_constraints = [
        ('unique_customer_number_company', 'unique(customer_number, company_id)',
         'رقم العميل يجب أن يكون فريداً لكل شركة!'),
        ('unique_accounting_partner', 'unique(partner_id)',
         'لا يمكن ربط أكثر من حساب كهرباء بنفس الشريك المحاسبي.'),
    ]

    def _create_dedicated_accounting_partner(self, owner_partner, customer_number):
        """Create a private accounting contact without changing the legal owner."""
        copy_vals = owner_partner.copy_data()[0]
        # Owner-level financial values must not be cloned into every utility
        # account. Account opening balances require an explicit account-level
        # allocation or opening journal entry.
        for field_name in ('open_balance', 'pec_credit', 'is_credit_raised', 'credit_raise_date'):
            copy_vals.pop(field_name, None)
        copy_vals.update({
            'name': _('%s - حساب كهرباء %s') % (owner_partner.name, customer_number),
            'parent_id': False,
            'is_subscriber': True,
            'customer_rank': max(owner_partner.customer_rank, 1),
        })
        return self.env['res.partner'].create(copy_vals)

    @api.constrains('partner_id', 'owner_partner_id')
    def _check_accounting_partner_identity(self):
        """Ensure the accounting partner belongs to exactly one utility account."""
        for customer in self:
            if not customer.partner_id:
                raise ValidationError(_('يجب تحديد شريك محاسبي للحساب الكهربائي.'))
            duplicate = self.search([
                ('partner_id', '=', customer.partner_id.id),
                ('id', '!=', customer.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'الشريك المحاسبي %s مرتبط مسبقًا بالحساب الكهربائي %s.'
                ) % (customer.partner_id.display_name, duplicate.customer_number))

    @api.model_create_multi
    def create(self, vals_list):
        """Create a dedicated accounting partner for every new utility account."""
        for vals in vals_list:
            if vals.get('customer_number', _('جديد')) == _('جديد'):
                vals['customer_number'] = self.env['ir.sequence'].next_by_code('utility.customer') or _('جديد')

            partner_id = vals.get('partner_id')
            owner_id = vals.get('owner_partner_id') or partner_id
            if not owner_id:
                raise ValidationError(_('يجب تحديد المالك القانوني للحساب الكهربائي.'))

            owner = self.env['res.partner'].browse(owner_id).exists()
            if not owner:
                raise ValidationError(_('المالك القانوني المحدد غير موجود.'))

            if not self.env.context.get('utility_account_partner_ready'):
                source_partner = self.env['res.partner'].browse(partner_id).exists() if partner_id else owner
                if not source_partner:
                    raise ValidationError(_('الشريك المحاسبي المحدد غير موجود.'))
                dedicated = self._create_dedicated_accounting_partner(
                    source_partner, vals['customer_number'])
                vals['owner_partner_id'] = owner.id
                vals['partner_id'] = dedicated.id
            else:
                vals['owner_partner_id'] = owner.id

        customers = super().create(vals_list)
        for customer in customers:
            customer.partner_id.sudo().write({
                'customer_rank': max(customer.partner_id.customer_rank, 1),
                'is_subscriber': True,
            })
        return customers

    def _get_effective_billing_period(self):
        """Return the mandatory billing cadence using geographic precedence."""
        self.ensure_one()
        recurring_type = False
        if self.area_id and self.area_id.recurring_rule_type:
            recurring_type = self.area_id.recurring_rule_type
        elif self.region_id and self.region_id.recurring_rule_type:
            recurring_type = self.region_id.recurring_rule_type
        elif self.contract_template_id and self.contract_template_id.recurring_rule_type:
            recurring_type = self.contract_template_id.recurring_rule_type
        return {'bi_monthly': 'biweekly'}.get(recurring_type, recurring_type)
    def write(self, vals):
        if 'partner_id' in vals:
            new_partner = self.env['res.partner'].browse(vals['partner_id']).exists()
            for customer in self:
                if not new_partner:
                    raise ValidationError(_('الشريك المحاسبي المحدد غير موجود.'))
                duplicate = self.search([
                    ('partner_id', '=', new_partner.id),
                    ('id', 'not in', self.ids),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        'لا يمكن استخدام الشريك المحاسبي %s؛ فهو مرتبط بالحساب %s.'
                    ) % (new_partner.display_name, duplicate.customer_number))
        res = super().write(vals)
        if 'partner_id' in vals:
            for customer in self:
                if customer.partner_id:
                    customer.partner_id.sudo().write({
                        'customer_rank': max(customer.partner_id.customer_rank, 1),
                        'is_subscriber': True,
                    })
        return res

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

    @api.depends('partner_id')
    def _compute_accounting_balance(self):
        MoveLine = self.env.get('account.move.line')
        if MoveLine is None:
            for rec in self:
                rec.accounting_balance = 0.0
            return

        partner_map = {rec.id: rec.partner_id.id for rec in self if rec.partner_id}
        if not partner_map:
            for rec in self:
                rec.accounting_balance = 0.0
            return

        balance_map = {cid: 0.0 for cid in partner_map}

        company_ids = list(set(rec.company_id.id for rec in self if rec.company_id))
        receivable_accounts = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_id', 'in', company_ids),
        ])
        if not receivable_accounts:
            for rec in self:
                rec.accounting_balance = 0.0
            return

        partner_ids = list(set(partner_map.values()))
        groups = MoveLine.sudo().read_group([
            ('partner_id', 'in', partner_ids),
            ('account_id', 'in', receivable_accounts.ids),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
        ], ['amount_residual:sum'], ['partner_id'])

        for group in groups:
            partner_id = group['partner_id'][0] if group['partner_id'] else False
            customer_id = next((cid for cid, pid in partner_map.items() if pid == partner_id), False)
            if customer_id:
                balance_map[customer_id] = group.get('amount_residual', 0.0)

        for rec in self:
            rec.accounting_balance = balance_map.get(rec.id, 0.0)

    def _get_receivable_balance(self, exclude_move_ids=None):
        """Return posted unreconciled receivables for this account partner only."""
        self.ensure_one()
        if not self.partner_id:
            return 0.0
        accounts = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_id', '=', self.company_id.id),
        ])
        if not accounts:
            return 0.0
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('account_id', 'in', accounts.ids),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
        ]
        if exclude_move_ids:
            domain.append(('move_id', 'not in', list(exclude_move_ids)))
        result = self.env['account.move.line'].sudo().read_group(
            domain, ['amount_residual:sum'], [])
        return result[0].get('amount_residual', 0.0) if result else 0.0

    @api.depends('partner_id', 'meter_id')
    def _compute_smart_buttons(self):
        So = self.env.get('sale.order')
        Reading = self.env.get('utility.reading')
        Payment = self.env.get('account.payment')
        Move = self.env.get('account.move')
        Replacement = self.env.get('utility.meter.replacement')
        Tamper = self.env.get('utility.tamper.case')

        customer_ids = self.ids
        partner_map = {rec.id: rec.partner_id.id for rec in self if rec.partner_id}

        counts = {cid: {'invoice': 0, 'accounting_invoice': 0, 'reading': 0,
                         'payment': 0, 'replacement': 0, 'tamper': 0} for cid in customer_ids}

        if So is not None and 'customer_id' in So._fields and customer_ids:
            groups = So.sudo().read_group(
                [('customer_id', 'in', customer_ids)],
                ['customer_id'],
                ['customer_id'],
            )
            for group in groups:
                customer_id = group['customer_id'][0] if group['customer_id'] else False
                if customer_id in counts:
                    counts[customer_id]['invoice'] = group['customer_id_count']
        if Reading is not None and 'account_id' in Reading._fields and customer_ids:
            groups = Reading.sudo().read_group(
                [('account_id', 'in', customer_ids)],
                ['account_id'],
                ['account_id'],
            )
            for g in groups:
                cid = g['account_id'][0] if g['account_id'] else False
                if cid in counts:
                    counts[cid]['reading'] = g['account_id_count']

        if (
            Payment is not None
            and 'utility_sale_order_id' in Payment._fields
            and customer_ids
        ):
            sale_order_ids = self.env['sale.order'].sudo().search([
                ('customer_id', 'in', customer_ids),
            ]).ids
            if sale_order_ids:
                groups = Payment.sudo().read_group(
                    [('utility_sale_order_id', 'in', sale_order_ids)],
                    ['utility_sale_order_id'],
                    ['utility_sale_order_id'],
                )
                so_to_customer = {}
                if sale_order_ids:
                    so_recs = self.env['sale.order'].sudo().browse(sale_order_ids)
                    so_to_customer = {so.id: so.customer_id.id for so in so_recs if so.customer_id}
                for g in groups:
                    so_id = g['utility_sale_order_id'][0] if g['utility_sale_order_id'] else False
                    cid = so_to_customer.get(so_id, False)
                    if cid in counts:
                        counts[cid]['payment'] += g['utility_sale_order_id_count']

        if Move is not None and partner_map:
            partner_ids = list(set(partner_map.values()))
            groups = Move.sudo().read_group([
                ('partner_id', 'in', partner_ids),
                ('state', '=', 'posted'),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
            ], ['partner_id'], ['partner_id'])
            partner_to_customer_ids = {}
            for customer_id, partner_id in partner_map.items():
                partner_to_customer_ids.setdefault(partner_id, []).append(customer_id)
            for group in groups:
                partner_id = group['partner_id'][0] if group['partner_id'] else False
                for customer_id in partner_to_customer_ids.get(partner_id, []):
                    counts[customer_id]['accounting_invoice'] = group['partner_id_count']

        if Replacement is not None and customer_ids:
            groups = Replacement.sudo().read_group(
                [('utility_account_id', 'in', customer_ids)],
                ['utility_account_id'],
                ['utility_account_id'],
            )
            for g in groups:
                cid = g['utility_account_id'][0] if g['utility_account_id'] else False
                if cid in counts:
                    counts[cid]['replacement'] = g['utility_account_id_count']

        if Tamper is not None and customer_ids:
            groups = Tamper.sudo().read_group(
                [('account_id', 'in', customer_ids)],
                ['account_id'],
                ['account_id'],
            )
            for group in groups:
                customer_id = group['account_id'][0] if group['account_id'] else False
                if customer_id in counts:
                    counts[customer_id]['tamper'] = group['account_id_count']
        for rec in self:
            c = counts.get(rec.id, {})
            rec.invoice_count = c.get('invoice', 0)
            rec.accounting_invoice_count = c.get('accounting_invoice', 0)
            rec.reading_count = c.get('reading', 0)
            rec.payment_count = c.get('payment', 0)
            rec.replacement_count = c.get('replacement', 0)
            rec.tamper_count = c.get('tamper', 0)

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
