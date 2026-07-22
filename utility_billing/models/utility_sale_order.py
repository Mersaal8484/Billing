from datetime import date, timedelta
from urllib.parse import quote
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilitySaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'utility.dropdown.mixin']
    _description = 'فاتورة كهرباء (أمر بيع)'

    customer_id = fields.Many2one('utility.customer', 'الحساب', index=True)
    meter_id = fields.Many2one('utility.meter', 'العداد', index=True)
    reading_id = fields.Many2one('utility.reading', 'قراءة العداد', index=True, ondelete='restrict')
    reading_component_ids = fields.One2many(
        'utility.bill.reading.component', 'sale_order_id',
        string='مكونات استهلاك الفاتورة', copy=False, readonly=True)
    reading_component_count = fields.Integer(
        'عدد مقاطع القراءة', compute='_compute_reading_component_count')
    available_billing_period_ids = fields.Many2many('date.range', compute='_compute_available_billing_period_ids')
    date_range_id = fields.Many2one('date.range', 'فترة الفوترة', index=True, required=True)
    route_id = fields.Many2one('utility.route', related='customer_id.route_id', store=True, string='خط السير', index=True)

    meter_image = fields.Binary(related='reading_id.meter_image', string='صورة العداد', readonly=False)
    reading_reviewer = fields.Many2one(related='reading_id.reviewer_id', string='مراجع القراءة')
    attachment_id = fields.Many2one('ir.attachment', string='ملف صورة القراءة الرسمي')



    transformer_reading_id = fields.Many2one('utility.reading', string='قراءة المحول/الخلية المرتبطة', compute='_compute_transformer_reading', store=True)

    workflow_process_id = fields.Many2one('sale.workflow.process', string='مسار العمل التلقائي', ondelete='restrict')
    all_qty_delivered = fields.Boolean(compute='_compute_all_qty_delivered', store=True)
    type_id = fields.Many2one('sale.order.type', string='نوع أمر البيع', default=lambda self: self._get_default_type())

    period_start = fields.Date('بداية الفترة')
    period_end = fields.Date('نهاية الفترة')
    previous_reading = fields.Float('القراءة السابقة')
    current_reading = fields.Float('القراءة الحالية')
    consumption = fields.Float('الاستهلاك')
    contract_template_id = fields.Many2one('utility.contract.template', 'قالب العقد', related='customer_id.contract_template_id', store=True)

    amount_energy = fields.Monetary('قيمة الطاقة', currency_field='currency_id')
    amount_service = fields.Monetary('رسم الخدمة الثابت', currency_field='currency_id')
    amount_discount = fields.Monetary('الخصومات', currency_field='currency_id')
    amount_local_fee = fields.Monetary('الرسوم المحلية', currency_field='currency_id')
    amount_penalty = fields.Monetary('الغرامات', compute='_compute_amount_penalty', store=True, currency_field='currency_id')
    penalty_ids = fields.One2many('utility.penalty', 'sale_order_id', string='الغرامات')
    utility_move_ids = fields.One2many(
        'account.move', 'utility_sale_order_id', string='فواتير الكهرباء المحاسبية')

    qr_code_value = fields.Char('بيانات QR', compute='_compute_qr_code', readonly=True)
    qr_code_url = fields.Char('رابط QR', compute='_compute_qr_code', readonly=True)
    disconnection_order_id = fields.Many2one('utility.service.order', string='أمر الفصل', readonly=True, copy=False)
    reconnection_order_id = fields.Many2one('utility.service.order', string='أمر إعادة الخدمة', readonly=True, copy=False)
    installment_plan_ids = fields.One2many('utility.installment.plan', 'sale_order_id', string='خطط التقسيط')
    installment_plan_count = fields.Integer('عدد خطط التقسيط', compute='_compute_installment_plan_count')


    amount_paid = fields.Monetary('المدفوع', compute='_compute_payment', store=True, currency_field='currency_id')
    balance_due = fields.Monetary('المتبقي', compute='_compute_payment', store=True, index=True, currency_field='currency_id')
    is_overdue = fields.Boolean('متأخر', compute='_compute_payment', store=True, index=True)

    previous_balance = fields.Monetary('رصيد المتأخرات (سابق)', compute='_compute_previous_balance', store=True, currency_field='currency_id')
    total_due_amount = fields.Monetary('إجمالي المطلوب سداده (فاتورة + متأخرات)', compute='_compute_total_due_amount', store=True, currency_field='currency_id')

    bill_state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكدة'),
        ('sent', 'مرسلة'),
        ('paid', 'مدفوعة'),
        ('overdue', 'متأخرة'),
        ('cancelled', 'ملغاة'),
    ], string='حالة الفاتورة', default='draft', tracking=True, compute='_compute_bill_state', store=True, index=True)

    @api.depends('reading_component_ids')
    def _compute_reading_component_count(self):
        for order in self:
            order.reading_component_count = len(order.reading_component_ids)

    def action_view_reading_components(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('مكونات استهلاك الفاتورة'),
            'res_model': 'utility.bill.reading.component',
            'view_mode': 'tree,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'create': False, 'delete': False},
        }

    @api.depends('customer_id.contract_template_id.recurring_rule_type', 'customer_id.area_id.recurring_rule_type', 'customer_id.region_id.recurring_rule_type')
    def _compute_available_billing_period_ids(self):
        for rec in self:
            account = rec.customer_id
            billing_period = False
            if account:
                if account.contract_template_id and account.contract_template_id.recurring_rule_type:
                    billing_period = account.contract_template_id.recurring_rule_type
                elif account.area_id and account.area_id.recurring_rule_type:
                    billing_period = account.area_id.recurring_rule_type
                elif account.region_id and account.region_id.recurring_rule_type:
                    billing_period = account.region_id.recurring_rule_type
            domain = self._get_open_period_domain(work_type='payment', billing_period=billing_period)
            rec.available_billing_period_ids = self.env['date.range'].search(domain)

    @api.onchange('customer_id')
    def _onchange_customer_id_date_range(self):
        available_periods = self.available_billing_period_ids
        if self.date_range_id and self.date_range_id not in available_periods:
            self.date_range_id = False
        return {'domain': {'date_range_id': [('id', 'in', available_periods.ids)]}}

    @api.onchange('date_range_id')
    def _onchange_date_range_id_set_period_dates(self):
        if self.date_range_id:
            if self.date_range_id.date_start:
                self.period_start = self.date_range_id.date_start
            if self.date_range_id.date_end:
                self.period_end = self.date_range_id.date_end

    @api.depends('name', 'customer_id.customer_number', 'partner_id.name', 'meter_id.meter_number', 'date_range_id.name', 'amount_total', 'total_due_amount', 'bill_state')
    def _compute_qr_code(self):
        for order in self:
            payload = '|'.join([
                'UTILITY-BILL',
                order.company_id.name or '',
                order.name or '',
                order.customer_id.customer_number or '',
                order.partner_id.name or '',
                order.meter_id.meter_number or '',
                order.date_range_id.name or '',
                'amount=%.2f' % (order.amount_total or 0.0),
                'due=%.2f' % (order.total_due_amount or order.amount_total or 0.0),
                'state=%s' % (order.bill_state or ''),
            ])
            order.qr_code_value = payload
            order.qr_code_url = '/report/barcode/?barcode_type=QR&value=%s' % quote(payload)
    @api.model
    def _get_default_type(self):
        return self.env['sale.order.type'].search([], limit=1)

    @api.depends('order_line.qty_delivered', 'order_line.product_uom_qty')
    def _compute_all_qty_delivered(self):
        for order in self:
            delivered = all(
                line.product_uom_qty <= (line.qty_delivered or 0.0)
                for line in order.order_line if line.product_id.type not in ('service', 'digital')
            )
            order.all_qty_delivered = delivered

    @api.depends('partner_id')
    def _compute_previous_balance(self):
        """Snapshot the customer's receivable balance before this bill is issued."""
        for order in self:
            order.previous_balance = order.partner_id.credit if order.partner_id else 0.0

    @api.depends('amount_total', 'previous_balance')
    def _compute_total_due_amount(self):
        for order in self:
            order.total_due_amount = order.amount_total + order.previous_balance

    @api.constrains('reading_id', 'state')
    def _check_unique_active_reading_bill(self):
        for order in self.filtered('reading_id'):
            duplicate = self.search([
                ('reading_id', '=', order.reading_id.id),
                ('id', '!=', order.id),
                ('state', '!=', 'cancel'),
            ], limit=1)
            if duplicate and order.state != 'cancel':
                raise ValidationError(_('لا يمكن إنشاء أكثر من فاتورة نشطة لنفس القراءة.'))

    def _prepare_invoice(self):
        res = super(UtilitySaleOrder, self)._prepare_invoice()
        res['utility_sale_order_id'] = self.id
        if self.workflow_process_id:
            res['workflow_process_id'] = self.workflow_process_id.id
        if self.current_reading:
            res['current_reading'] = self.current_reading
        if self.previous_reading:
            res['previous_reading'] = self.previous_reading
        if self.consumption:
            res['consumption'] = self.consumption
        if self.workflow_process_id and self.workflow_process_id.invoice_date_is_order_date:
            res['invoice_date'] = self.date_order.date()
        if self.type_id:
            res['sale_type_id'] = self.type_id.id
            if self.type_id.journal_id:
                res['journal_id'] = self.type_id.journal_id.id
        return res

    @api.onchange('workflow_process_id')
    def _onchange_workflow_process_id(self):
        if self.workflow_process_id:
            self.picking_policy = self.workflow_process_id.picking_policy

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id and self.partner_id.sale_type:
            self.type_id = self.partner_id.sale_type

    @api.onchange('type_id')
    def onchange_type_id(self):
        if self.type_id:
            if self.type_id.warehouse_id:
                self.warehouse_id = self.type_id.warehouse_id
            if self.type_id.picking_policy:
                self.picking_policy = self.type_id.picking_policy
            if self.type_id.payment_term_id:
                self.payment_term_id = self.type_id.payment_term_id.id
            if self.type_id.pricelist_id:
                self.pricelist_id = self.type_id.pricelist_id.id
            if self.type_id.incoterm_id:
                self.incoterm = self.type_id.incoterm_id.id

    @api.onchange('order_line')
    def _onchange_order_line(self):
        if not self.type_id:
            self.match_order_type()

    def match_order_type(self):
        order_types = self.env['sale.order.type'].search([])
        for order_type in order_types:
            if order_type.matches_order(self):
                self.type_id = order_type
                self.onchange_type_id()
                break

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/' and vals.get('type_id'):
                sale_type = self.env['sale.order.type'].browse(vals['type_id'])
                if sale_type.sequence_id:
                    vals['name'] = sale_type.sequence_id.next_by_id()
        return super(UtilitySaleOrder, self).create(vals_list)

    def action_confirm(self):
        # 1. Prepare bulk contract creation for lines with is_contract
        contracts_to_create = []
        lines_mapping = []
        for rec in self:
            order_lines = rec.order_line.filtered(lambda r: r.product_id.is_contract)
            for line in order_lines:
                contracts_to_create.append({
                    'name': f'{rec.name} - عقد كهرباء',
                    'partner_id': rec.partner_id.id,
                    'contract_template_id': line.product_id.contract_template_id.id if line.product_id.contract_template_id else False,
                })
                lines_mapping.append(line)

        # 2. Execute Bulk Operation
        if contracts_to_create:
            contracts = self.env['account.analytic.account'].create(contracts_to_create)
            # Map created contracts back to their lines
            for line, contract in zip(lines_mapping, contracts):
                line.contract_id = contract.id
            # Trigger recurring invoicing if available
            if hasattr(contracts, 'recurring_create_invoice'):
                contracts.recurring_create_invoice()

        res = super(UtilitySaleOrder, self).action_confirm()
        self._create_invoice_notifications()
        return res

    def _create_notification_logs(self, event_type, body, sms_config_key=False, subject=False):
        Notification = self.env['utility.notification.log'].sudo()
        params = self.env['ir.config_parameter'].sudo()
        for order in self.filtered('customer_id'):
            Notification.create_log(
                event_type, body(order), record=order, customer=order.customer_id,
                channel='portal', subject=subject
            )
            if sms_config_key and params.get_param(sms_config_key, False):
                Notification.create_log(
                    event_type, body(order), record=order, customer=order.customer_id,
                    channel='sms', subject=subject
                )

    def _create_invoice_notifications(self):
        self._create_notification_logs(
            'invoice_created',
            lambda order: _('تم إصدار فاتورة الكهرباء %s بمبلغ %.2f. المتبقي %.2f.')
                          % (order.name, order.amount_total, order.balance_due),
            sms_config_key='utility.send_sms_on_invoice',
            subject=_('إصدار فاتورة كهرباء'),
        )

    def action_register_utility_payment(self):
        """Open payment creation wizard pre-filled with customer bill details and collector's dedicated cash journal."""
        self.ensure_one()
        current_user = self.env.user
        journal = current_user.collection_journal_id

        if not journal:
            staff = self.env['utility.staff'].search([
                ('user_id', '=', current_user.id),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            if staff:
                staff._auto_create_collector_journal()
                journal = staff.collection_journal_id

        if not journal:
            code = ('C%s' % current_user.id)[:5].upper()
            journal_name = 'يومية تحصيل - %s' % current_user.name
            journal = self.env['account.journal'].search([
                ('company_id', '=', self.company_id.id),
                ('type', '=', 'cash'),
                '|', ('code', '=', code), ('name', '=', journal_name)
            ], limit=1)
            if not journal:
                acc_name = 'حساب صندوق - %s' % current_user.name
                cash_acc = self.env['account.account'].search([
                    ('name', '=', acc_name),
                    ('company_id', '=', self.company_id.id)
                ], limit=1)
                if not cash_acc:
                    code_num = str(current_user.id).zfill(3)
                    cash_acc = self.env['account.account'].create({
                        'name': acc_name,
                        'code': '101%s' % code_num[-3:],
                        'account_type': 'asset_cash',
                        'company_id': self.company_id.id,
                    })
                journal = self.env['account.journal'].create({
                    'name': journal_name,
                    'code': code,
                    'type': 'cash',
                    'company_id': self.company_id.id,
                    'default_account_id': cash_acc.id,
                })
            current_user.sudo().write({'collection_journal_id': journal.id})

        if journal:
            company = journal.company_id
            if not company.account_journal_payment_debit_account_id or not company.account_journal_payment_credit_account_id:
                outstanding_acc = self.env['account.account'].search([
                    ('name', 'ilike', 'مستحق'),
                    ('company_id', 'in', (company.id, False))
                ], limit=1) or self.env['account.account'].search([
                    ('account_type', 'in', ('asset_current', 'asset_cash')),
                    ('company_id', 'in', (company.id, False))
                ], limit=1)
                if not outstanding_acc:
                    outstanding_acc = self.env['account.account'].create({
                        'name': 'حساب الإيصالات والدفعات المستحقة',
                        'code': '101200',
                        'account_type': 'asset_current',
                        'company_id': company.id,
                    })
                c_vals = {}
                if not company.account_journal_payment_debit_account_id:
                    c_vals['account_journal_payment_debit_account_id'] = outstanding_acc.id
                if not company.account_journal_payment_credit_account_id:
                    c_vals['account_journal_payment_credit_account_id'] = outstanding_acc.id
                if c_vals:
                    company.sudo().write(c_vals)

            j_vals = {}
            acc_name = 'حساب صندوق - %s' % current_user.name
            cash_acc = journal.default_account_id
            if not cash_acc or (current_user.name and current_user.name not in cash_acc.name):
                cash_acc = self.env['account.account'].search([
                    ('name', '=', acc_name),
                    ('company_id', '=', company.id)
                ], limit=1)
                if not cash_acc:
                    code_num = str(current_user.id).zfill(3)
                    cash_acc = self.env['account.account'].create({
                        'name': acc_name,
                        'code': '101%s' % code_num[-3:],
                        'account_type': 'asset_cash',
                        'company_id': company.id,
                    })
                j_vals['default_account_id'] = cash_acc.id

            LineModel = self.env['account.payment.method.line']
            acc_field = 'payment_account_id' if hasattr(LineModel, 'payment_account_id') else ('outstanding_account_id' if hasattr(LineModel, 'outstanding_account_id') else False)
            target_out_acc = company.account_journal_payment_debit_account_id.id if company.account_journal_payment_debit_account_id else (cash_acc.id if cash_acc else False)

            if not journal.inbound_payment_method_line_ids:
                manual_inbound = self.env['account.payment.method'].search([
                    ('payment_type', '=', 'inbound'),
                    ('code', '=', 'manual')
                ], limit=1)
                if manual_inbound:
                    m_line = {'name': 'يدوي', 'payment_method_id': manual_inbound.id}
                    if acc_field and target_out_acc: m_line[acc_field] = target_out_acc
                    j_vals['inbound_payment_method_line_ids'] = [(0, 0, m_line)]
            elif acc_field and target_out_acc:
                for line in journal.inbound_payment_method_line_ids:
                    if not getattr(line, acc_field, False):
                        line.sudo().write({acc_field: target_out_acc})

            if not journal.outbound_payment_method_line_ids:
                manual_outbound = self.env['account.payment.method'].search([
                    ('payment_type', '=', 'outbound'),
                    ('code', '=', 'manual')
                ], limit=1)
                if manual_outbound:
                    m_line = {'name': 'يدوي', 'payment_method_id': manual_outbound.id}
                    if acc_field and target_out_acc: m_line[acc_field] = target_out_acc
                    j_vals['outbound_payment_method_line_ids'] = [(0, 0, m_line)]
            elif acc_field and target_out_acc:
                for line in journal.outbound_payment_method_line_ids:
                    if not getattr(line, acc_field, False):
                        line.sudo().write({acc_field: target_out_acc})

            if j_vals:
                journal.sudo().write(j_vals)

        return {
            'name': _('تسجيل تحصيل الفاتورة'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_payment_type': 'inbound',
                'default_partner_type': 'customer',
                'default_partner_id': self.partner_id.id,
                'default_amount': self.balance_due if self.balance_due > 0 else self.amount_total,
                'default_utility_sale_order_id': self.id,
                'default_journal_id': journal.id if journal else False,
            }
        }

    def _create_overdue_notifications(self):
        self._create_notification_logs(
            'bill_overdue',
            lambda order: _('الفاتورة %s متأخرة وبها مبلغ مستحق %.2f. يرجى السداد لتجنب الفصل.')
                          % (order.name, order.balance_due),
            sms_config_key='utility.send_sms_on_overdue',
            subject=_('تنبيه فاتورة متأخرة'),
        )

    BILL_PROTECTED_FIELDS = {
        'customer_id', 'meter_id', 'reading_id', 'date_range_id',
        'period_start', 'period_end', 'previous_reading', 'current_reading',
        'consumption', 'contract_template_id', 'order_line',
        'amount_energy', 'amount_service', 'amount_discount',
        'amount_local_fee', 'amount_penalty',
    }

    def write(self, vals):
        if vals.get('state') == 'cancel':
            for order in self:
                component_readings = order.reading_component_ids.mapped('reading_id')
                closing_readings = component_readings.filtered(
                    lambda reading: reading.reading_purpose == 'replacement_closing')
                if closing_readings:
                    closing_readings.with_context(_bypass_reading_protection=True).write({
                        'state': 'approved',
                        'billing_anchor_id': False,
                        'included_sale_order_id': False,
                        'billing_error': False,
                    })
                if order.reading_id:
                    order.reading_id.with_context(_bypass_reading_protection=True).write({
                        'state': 'approved',
                        'included_sale_order_id': False,
                        'billing_error': False,
                    })
        # Allow system/sudo writes, or specific status/payment updates
        if not self.env.is_superuser() and not self.env.context.get('allow_status_update'):
            for order in self:
                if order.bill_state != 'draft':
                    changed = self.BILL_PROTECTED_FIELDS & set(vals)
                    if changed:
                        raise ValidationError(
                            'لا يمكن تعديل الحقول المالية أو الفنية للفاتورة [%s] '
                            'لأن حالتها "%s". الرجاء إلغاء الفاتورة أو إنشاء تسوية بدلاً من ذلك.'
                            % (order.name, order.bill_state)
                        )
        return super(UtilitySaleOrder, self).write(vals)

    def action_draft(self):
        for order in self:
            posted = order.invoice_ids.filtered(lambda i: i.state == 'posted')
            if posted:
                raise ValidationError(
                    'لا يمكن إعادة الفاتورة للمسودة، يوجد فواتير محاسبية مرحلة. '
                    'قم بإلغائها أولاً.')
            if order.bill_state in ('paid', 'cancelled'):
                raise ValidationError(
                    'لا يمكن إعادة فاتورة %s إلى المسودة.' % order.bill_state)
        res = super(UtilitySaleOrder, self).action_draft()
        for order in self:
            if order.reading_id and order.reading_id.state == 'billed':
                order.reading_id.sudo().with_context(
                    _bypass_reading_protection=True).write({'state': 'under_review'})
        return res

    @api.depends('meter_id', 'date_range_id', 'reading_id')
    def _compute_transformer_reading(self):
        UtilityReading = self.env.get('utility.reading')
        for order in self:
            if order.meter_id and order.meter_id.transformer_id and UtilityReading:
                tr = UtilityReading.search([
                    ('reading_category', '=', 'transformer'),
                    ('meter_id.transformer_id', '=', order.meter_id.transformer_id.id),
                    ('date_range_id', '=', order.date_range_id.id),
                    ('state', '=', 'approved'),
                ], limit=1)
                if not tr:
                    tr = UtilityReading.search([
                        ('reading_category', '=', 'transformer'),
                        ('meter_id.transformer_id', '=', order.meter_id.transformer_id.id),
                        ('state', '=', 'approved'),
                    ], order='reading_date desc', limit=1)
                order.transformer_reading_id = tr.id if tr else False
            else:
                order.transformer_reading_id = False

    def _get_posted_utility_moves(self):
        self.ensure_one()
        return (self.invoice_ids | self.utility_move_ids).filtered(
            lambda move: move.state == 'posted' and move.move_type in ('out_invoice', 'out_refund')
        )

    @api.depends(
        'amount_total', 'amount_penalty', 'state', 'date_order',
        'invoice_ids.state', 'invoice_ids.payment_state',
        'invoice_ids.amount_total', 'invoice_ids.amount_residual', 'invoice_ids.move_type',
        'utility_move_ids.state', 'utility_move_ids.payment_state',
        'utility_move_ids.amount_total', 'utility_move_ids.amount_residual', 'utility_move_ids.move_type')
    def _compute_payment(self):
        for r in self:
            posted_moves = r._get_posted_utility_moves()
            if posted_moves:
                signed_total = sum(
                    -move.amount_total if move.move_type == 'out_refund' else move.amount_total
                    for move in posted_moves
                )
                signed_residual = sum(
                    -move.amount_residual if move.move_type == 'out_refund' else move.amount_residual
                    for move in posted_moves
                )
                r.amount_paid = signed_total - signed_residual
                r.balance_due = signed_residual
            else:
                r.amount_paid = 0.0
                r.balance_due = r.amount_total + r.amount_penalty
            r.is_overdue = r.balance_due > 0 and r.date_order and r.date_order.date() < date.today()

    @api.depends('state', 'is_overdue', 'balance_due', 'invoice_ids.state', 'invoice_ids.payment_state', 'utility_move_ids.state', 'utility_move_ids.payment_state')
    def _compute_bill_state(self):
        for r in self:
            if r.state == 'cancel':
                r.bill_state = 'cancelled'
            elif r.state == 'draft':
                r.bill_state = 'draft'
            else:
                posted_invoices = r._get_posted_utility_moves()
                # If fully paid (or amount is 0 and it is invoiced)
                if posted_invoices and r.balance_due <= 0:
                    r.bill_state = 'paid'
                elif r.is_overdue:
                    r.bill_state = 'overdue'
                elif posted_invoices:
                    r.bill_state = 'sent'
                elif r.state == 'sale':
                    r.bill_state = 'confirmed'
                else:
                    r.bill_state = 'draft'

    @api.depends('penalty_ids.amount', 'penalty_ids.state')
    def _compute_amount_penalty(self):
        for r in self:
            r.amount_penalty = sum(
                r.penalty_ids.filtered(lambda p: p.state == 'applied').mapped('amount')
            )

    def _compute_installment_plan_count(self):
        for order in self:
            order.installment_plan_count = len(order.installment_plan_ids)

    def action_create_installment_plan(self):
        self.ensure_one()
        if self.env.user.prevent_installment:
            raise ValidationError(_('هذا المستخدم غير مسموح له بإنشاء خطط تقسيط.'))
        if not self.customer_id:
            raise ValidationError(_('لا يمكن إنشاء خطة تقسيط دون حساب كهرباء مرتبط بالفاتورة.'))
        if self.balance_due <= 0:
            raise ValidationError(_('لا توجد مبالغ متبقية لتقسيطها.'))
        active_plan = self.installment_plan_ids.filtered(lambda p: p.state in ('draft', 'active'))[:1]
        if active_plan:
            plan = active_plan
        else:
            plan = self.env['utility.installment.plan'].create({
                'sale_order_id': self.id,
                'amount_total': self.balance_due,
                'installment_count': 3,
                'start_date': fields.Date.context_today(self),
            })
            plan.action_generate_lines()
        return {
            'type': 'ir.actions.act_window',
            'name': plan.name,
            'res_model': 'utility.installment.plan',
            'res_id': plan.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_installment_plans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('خطط التقسيط'),
            'res_model': 'utility.installment.plan',
            'view_mode': 'tree,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id, 'default_amount_total': self.balance_due},
        }
    def _open_service_order_action(self, service_order):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': service_order.order_number,
            'res_model': 'utility.service.order',
            'res_id': service_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _find_open_service_order(self, service_type):
        self.ensure_one()
        return self.env['utility.service.order'].search([
            ('customer_id', '=', self.customer_id.id),
            ('service_type', '=', service_type),
            ('state', 'not in', ['completed', 'cancelled']),
        ], limit=1)

    def action_create_disconnection_order(self):
        self.ensure_one()
        if not self.customer_id:
            raise ValidationError(_('لا يمكن إنشاء أمر فصل دون حساب كهرباء مرتبط بالفاتورة.'))
        if self.balance_due <= 0 or self.bill_state == 'paid':
            raise ValidationError(_('لا يمكن إنشاء أمر فصل لفاتورة مدفوعة بالكامل.'))
        if self.disconnection_order_id and self.disconnection_order_id.state != 'cancelled':
            return self._open_service_order_action(self.disconnection_order_id)
        duplicate = self._find_open_service_order('disconnection')
        if duplicate:
            self.disconnection_order_id = duplicate.id
            return self._open_service_order_action(duplicate)
        order = self.env['utility.service.order'].create({
            'service_type': 'disconnection',
            'priority': 'high',
            'customer_id': self.customer_id.id,
            'meter_id': self.meter_id.id,
            'description': _('فصل خدمة بسبب متأخرات الفاتورة %s بمبلغ %.2f.') % (self.name, self.balance_due),
        })
        self.disconnection_order_id = order.id
        return self._open_service_order_action(order)

    def action_create_reconnection_order(self):
        self.ensure_one()
        if not self.customer_id:
            raise ValidationError(_('لا يمكن إنشاء أمر إعادة خدمة دون حساب كهرباء مرتبط.'))
        if self.balance_due > 0:
            raise ValidationError(_('لا يمكن إنشاء أمر إعادة خدمة قبل تسوية المتأخرات.'))
        if self.reconnection_order_id and self.reconnection_order_id.state != 'cancelled':
            return self._open_service_order_action(self.reconnection_order_id)
        duplicate = self._find_open_service_order('reconnection')
        if duplicate:
            self.reconnection_order_id = duplicate.id
            return self._open_service_order_action(duplicate)
        order = self.env['utility.service.order'].create({
            'service_type': 'reconnection',
            'priority': 'normal',
            'customer_id': self.customer_id.id,
            'meter_id': self.meter_id.id,
            'description': _('إعادة خدمة بعد تسوية الفاتورة %s.') % self.name,
        })
        self.reconnection_order_id = order.id
        return self._open_service_order_action(order)

    @api.model
    def cron_create_disconnection_orders(self):
        params = self.env['ir.config_parameter'].sudo()
        days = int(params.get_param('utility.auto_disconnection_days', 90))
        batch_size = int(params.get_param('utility.disconnection_batch_size', 200))
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=days)
        orders = self.search([
            ('customer_id', '!=', False),
            ('bill_state', '=', 'overdue'),
            ('balance_due', '>', 0),
            ('date_order', '<=', cutoff),
            ('disconnection_order_id', '=', False),
        ], limit=batch_size, order='date_order asc, id asc')
        created = self.env['utility.service.order']
        for order in orders:
            existing = order._find_open_service_order('disconnection')
            if existing:
                order.disconnection_order_id = existing.id
                continue
            service_order = self.env['utility.service.order'].create({
                'service_type': 'disconnection',
                'priority': 'high',
                'customer_id': order.customer_id.id,
                'meter_id': order.meter_id.id,
                'description': _('فصل خدمة آلي بسبب متأخرات الفاتورة %s بمبلغ %.2f بعد %s يوم.')
                               % (order.name, order.balance_due, days),
            })
            order.disconnection_order_id = service_order.id
            created |= service_order
        return len(created)
    def action_recalculate_bill(self):
        for order in self:
            if order.state == 'draft':
                order._calculate_amounts()

    def _calculate_amounts(self):
        # FIX-6: guard — لا يُسمح بتعديل بنود فاتورة مؤكدة أو مرحّلة
        if self.state not in ('draft', 'sent'):
            raise ValidationError(
                'لا يمكن إعادة حساب بنود الفاتورة [%s] لأنها في حالة "%s".\nاستخدم إشعار الدائن (Credit Note) لتصحيح المبالغ.' % (self.name, self.state)
            )
        """حساب مبالغ الفاتورة وفق قالب العقد.
        مصدر الحقيقة للتسعير: قالب العقد (utility.contract.template).
        """
        self.ensure_one()
        account = self.customer_id
        category = account.subscriber_id if account else False
        consumption = self.consumption or 0.0
        lines = []
        template = account.contract_template_id if account else False

        # إعادة ضبط الخانات
        self.amount_energy = 0.0
        self.amount_service = 0.0
        self.amount_discount = 0.0
        self.amount_local_fee = 0.0

        Product = self.env['product.product']
        kwh_product = self.env.ref(
            'utility_core.utility_product_kwh', raise_if_not_found=False
        ) or Product.search([('type', '=', 'service')], limit=1)
        fixed_product = self.env.ref(
            'utility_core.utility_product_fixed_fee', raise_if_not_found=False
        ) or Product.search([('type', '=', 'service')], limit=1)
        service_product = self.env.ref(
            'utility_core.utility_product_service_charge', raise_if_not_found=False
        ) or Product.search([('type', '=', 'service')], limit=1)

        # ─────────────────────────────────────────────────────────────
        # المسار الأساسي: حساب المبالغ من خلال قالب العقد
        # ─────────────────────────────────────────────────────────────
        if template:
            for line in template.line_ids.sorted('sequence'):
                # تجاوز الاستهلاك العادي إذا كان التسعير بالشرائح أو مستوى واحد
                if template.pricing_mode in ('block', 'tier') and line.meter_line_type == 'consumption':
                    continue

                # إذا كان الخصم يعتمد على شرائح، نحسب الوحدات هنا ونولد سطوراً مفصلة لكل شريحة خصم
                if line.meter_line_type == 'discount' and template.discount_block_ids:
                    discount_units = 0.0
                    name = line.name or line.product_id.name or ''
                    if line.qty_formula_id:
                        discount_units, name = line.qty_formula_id.execute(
                            consumption=consumption,
                            previous_reading=self.previous_reading,
                            current_reading=self.current_reading,
                            template=template,
                            account=account,
                            category=category,
                            line=line,
                        )
                    elif template and template.discount_formula_id:
                        discount_units, name = template.discount_formula_id.execute(
                            consumption=consumption,
                            previous_reading=self.previous_reading,
                            current_reading=self.current_reading,
                            template=template,
                            account=account,
                            category=category,
                            line=line,
                        )
                    discount_units = max(discount_units or 0.0, 0.0)
                    if discount_units > 0:
                        sponsor_id = template.sponsor_id.id if template.sponsor_id else False
                        product_id = line.product_id.id if line.product_id else False
                        d_lines, d_amount = self._prepare_block_discount_lines(template, discount_units, name, product_id, sponsor_id)
                        lines.extend(d_lines)
                        self._accumulate_amount('discount', d_amount)
                    continue

                qty, price, name, product_id, sponsor_id = self._compute_line_amounts(
                    line, consumption, account, category, template
                )
                if not qty and not price:
                    continue
                amount = qty * price
                lines.append((0, 0, {
                    'product_id': product_id or kwh_product.id if kwh_product else False,
                    'name': name or line.name or line.product_id.name or '',
                    'product_uom_qty': qty,
                    'price_unit': price,
                    'sponsor_id': sponsor_id,
                    'meter_line_type': line.meter_line_type,
                    'tax_id': [(5, 0, 0)],
                }))
                self._accumulate_amount(line.meter_line_type, amount)

            # ── التسعير بالشرائح (block) أو المستوى (tier) ────────────────────────────────
            if template.pricing_mode in ('block', 'tier') and consumption > 0:
                if template.pricing_mode == 'block':
                    block_lines, block_amount = self._prepare_block_consumption_lines(
                        template, consumption, kwh_product
                    )
                else:
                    block_lines, block_amount = self._prepare_tier_consumption_lines(
                        template, consumption, kwh_product
                    )
                lines.extend(block_lines)
                self.amount_energy += block_amount

            # الرسوم المحلية التلقائية (المعلم، النظافة، المحلي) من القالب والإعدادات
            existing_local_fee_types = [l.meter_line_type for l in template.line_ids if l.meter_line_type in ('mu_allim', 'cleaning', 'municipality')]
            company = self.company_id or self.env.company

            if 'mu_allim' not in existing_local_fee_types and template.local_fee_mu_allim > 0:
                prod = company.mu_allim_product_id or service_product
                amount = consumption * template.local_fee_mu_allim
                if amount > 0:
                    lines.append((0, 0, {
                        'product_id': prod.id,
                        'name': 'رسم المعلم',
                        'product_uom_qty': consumption,
                        'price_unit': template.local_fee_mu_allim,
                        'meter_line_type': 'mu_allim',
                        'tax_id': [(5, 0, 0)],
                    }))
                    self.amount_local_fee += amount

            if 'cleaning' not in existing_local_fee_types and template.local_fee_cleaning > 0:
                prod = company.cleaning_product_id or service_product
                amount = consumption * template.local_fee_cleaning
                if amount > 0:
                    lines.append((0, 0, {
                        'product_id': prod.id,
                        'name': 'رسم النظافة',
                        'product_uom_qty': consumption,
                        'price_unit': template.local_fee_cleaning,
                        'meter_line_type': 'cleaning',
                        'tax_id': [(5, 0, 0)],
                    }))
                    self.amount_local_fee += amount

            if 'municipality' not in existing_local_fee_types and template.local_fee_per_kwh > 0:
                prod = company.local_fee_product_id or service_product
                amount = consumption * template.local_fee_per_kwh
                if amount > 0:
                    lines.append((0, 0, {
                        'product_id': prod.id,
                        'name': 'رسم محلي (مجالس محلية)',
                        'product_uom_qty': consumption,
                        'price_unit': template.local_fee_per_kwh,
                        'meter_line_type': 'municipality',
                        'tax_id': [(5, 0, 0)],
                    }))
                    self.amount_local_fee += amount

        # ─────────────────────────────────────────────────────────────
        # حدود الفوترة (min/max) — تُطبَّق على الإجمالي قبل الخصم
        # ─────────────────────────────────────────────────────────────
        if template:
            pre_total = (self.amount_energy + self.amount_service + self.amount_local_fee)
            if template.min_charge and pre_total < template.min_charge:
                # إضافة بند فرق للحد الأدنى
                lines.append((0, 0, {
                    'product_id': fixed_product.id if fixed_product else False,
                    'name': f'تسوية إلى الحد الأدنى ({template.min_charge})',
                    'product_uom_qty': 1,
                    'price_unit': template.min_charge - pre_total,
                    'meter_line_type': 'fixed_fee',
                    'tax_id': [(5, 0, 0)],
                }))
                self.amount_service += template.min_charge - pre_total
            elif template.max_charge and pre_total > template.max_charge:
                # تخفيض إلى الحد الأقصى كبند خصم
                lines.append((0, 0, {
                    'product_id': fixed_product.id if fixed_product else False,
                    'name': f'تسوية إلى الحد الأقصى ({template.max_charge})',
                    'product_uom_qty': 1,
                    'price_unit': template.max_charge - pre_total,
                    'meter_line_type': 'discount',
                    'tax_id': [(5, 0, 0)],
                }))
                self.amount_discount += pre_total - template.max_charge

        self.order_line = [(5, 0, 0)] + lines

    def _prepare_block_consumption_lines(self, template, consumption, kwh_product):
        """Build consumption lines for block pricing and reject uncovered kWh."""
        self.ensure_one()
        if not template.block_ids:
            raise ValidationError(
                _('قالب العقد "%s" مضبوط على التسعير بالشرائح، لكن لا توجد شرائح معرفة.')
                % template.name
            )

        lines = []
        priced_qty = 0.0
        amount_energy = 0.0
        for block in template.block_ids.sorted(lambda b: (b.from_kwh, b.sequence, b.id)):
            block_from = block.from_kwh or 0.0
            block_to = block.to_kwh if block.to_kwh > 0 else consumption
            qty_in_block = max(0.0, min(consumption, block_to) - block_from)
            if qty_in_block <= 0:
                continue

            amount = qty_in_block * block.price_per_kwh
            block_to_label = f'{block.to_kwh:.0f}' if block.to_kwh > 0 else _('ما لا نهاية')
            block_name = block.name or _('الشريحة %s') % block.sequence
            lines.append((0, 0, {
                'product_id': kwh_product.id if kwh_product else False,
                'name': _('%s: %.0f - %s kWh') % (block_name, block.from_kwh or 0.0, block_to_label),
                'product_uom_qty': qty_in_block,
                'price_unit': block.price_per_kwh,
                'meter_line_type': 'consumption',
                'tax_id': [(5, 0, 0)],
            }))
            priced_qty += qty_in_block
            amount_energy += amount

        if consumption - priced_qty > 0.000001:
            raise ValidationError(
                _('قالب العقد "%s" لا يغطي كامل الاستهلاك بالشرائح. الاستهلاك: %.2f kWh، المسعر: %.2f kWh.')
                % (template.name, consumption, priced_qty)
            )
        return lines, amount_energy

    def _prepare_block_discount_lines(self, template, discount_units, base_name, product_id, sponsor_id):
        """إعداد بنود الخصم بالتفصيل لكل شريحة لتظهر على الفاتورة بشكل واضح"""
        lines = []
        amount_discount = 0.0
        priced_units = 0.0
        for block in template.discount_block_ids.sorted(lambda b: (b.from_kwh, b.sequence, b.id)):
            block_from = block.from_kwh or 0.0
            block_to = block.to_kwh if block.to_kwh > 0 else discount_units
            qty_in_block = max(0.0, min(discount_units, block_to) - block_from)
            if qty_in_block <= 0:
                continue

            price = -abs(block.price_per_kwh)
            amount = qty_in_block * price
            block_name = f"{base_name or 'خصم استهلاك مدعوم'} - شريحة الخصم ({(block.from_kwh or 0.0):.0f} إلى {block.to_kwh if block.to_kwh > 0 else 'ما لا نهاية'})"
            lines.append((0, 0, {
                'product_id': product_id,
                'name': block_name,
                'product_uom_qty': qty_in_block,
                'price_unit': price,
                'sponsor_id': sponsor_id,
                'meter_line_type': 'discount',
                'tax_id': [(5, 0, 0)],
            }))
            amount_discount += amount
            priced_units += qty_in_block

        if discount_units - priced_units > 0.000001:
            raise ValidationError(
                _('قالب العقد "%s" لا يغطي كامل وحدات الخصم بالشرائح. وحدات الخصم: %.2f، المسعر: %.2f.')
                % (template.name, discount_units, priced_units)
            )
        return lines, amount_discount

    def _prepare_tier_consumption_lines(self, template, consumption, kwh_product):
        """Build consumption line for tier pricing (single level)."""
        lines = []
        amount_energy = 0.0
        applicable_block = None

        for block in template.block_ids.sorted(lambda b: (b.from_kwh, b.sequence, b.id)):
            if block.from_kwh <= consumption and (block.to_kwh >= consumption or block.to_kwh == 0.0):
                applicable_block = block
                break

        if not applicable_block and template.block_ids:
            applicable_block = template.block_ids.sorted(lambda b: (b.from_kwh, b.sequence, b.id))[-1]

        price = applicable_block.price_per_kwh if applicable_block else (template.price_per_kwh or 0.0)
        name = applicable_block.name if applicable_block and applicable_block.name else 'استهلاك (مستوى واحد)'

        if price > 0:
            amount = consumption * price
            lines.append((0, 0, {
                'product_id': kwh_product.id if kwh_product else False,
                'name': name,
                'product_uom_qty': consumption,
                'price_unit': price,
                'meter_line_type': 'consumption',
                'tax_id': [(5, 0, 0)],
            }))
            amount_energy += amount

        return lines, amount_energy

    def _compute_line_amounts(self, line, consumption, account, category, template):
        """حساب (qty, price, name, product_id, sponsor_id) لبند قالب عقد واحد."""
        qty = 0.0
        price = 0.0
        name = line.name or line.product_id.name or ''
        product_id = line.product_id.id if line.product_id else False
        sponsor_id = False

        # السعر من القالب (مصدر الحقيقة) — line.specific_price للـ override
        template_price = template.price_per_kwh if template else 0.0
        template_service = template.service_charge if template else 0.0

        if line.meter_line_type == 'consumption':
            # حساب الكمية — من المعادلة أو مباشرة
            if line.qty_formula_id:
                qty, name = line.qty_formula_id.execute(
                    consumption=consumption,
                    previous_reading=self.previous_reading,
                    current_reading=self.current_reading,
                    template=template,
                    account=account,
                    category=category,
                    line=line,
                )
            else:
                qty = consumption
            price = line.specific_price or template_price

        elif line.meter_line_type in ('fixed_fee', 'service_charge'):
            # fixed_fee و service_charge كلاهما يمثلان رسم الخدمة الثابت
            if line.qty_formula_id:
                qty, name = line.qty_formula_id.execute(
                    consumption=consumption,
                    previous_reading=self.previous_reading,
                    current_reading=self.current_reading,
                    template=template,
                    account=account,
                    category=category,
                    line=line,
                )
            else:
                qty = 1.0
            price = line.specific_price or template_service

        elif line.meter_line_type in ('mu_allim', 'cleaning', 'municipality'):
            qty = consumption
            if line.specific_price:
                price = line.specific_price
            elif template:
                if line.meter_line_type == 'mu_allim':
                    price = template.local_fee_mu_allim
                elif line.meter_line_type == 'cleaning':
                    price = template.local_fee_cleaning
                else:
                    price = template.local_fee_per_kwh
            else:
                price = 0.0
            if not line.name:
                type_labels = {
                    'municipality': 'رسم مجلس محلي',
                    'mu_allim': 'رسم المعلم',
                    'cleaning': 'رسم نظافة',
                }
                name = type_labels.get(line.meter_line_type, 'رسم محلي')

        elif line.meter_line_type == 'discount':
            # الخصم: المعادلة تحدد عدد الوحدات، وشرائح الخصم تحدد قيمة الخصم لكل وحدة.
            discount_units = 0.0
            if line.qty_formula_id:
                discount_units, name = line.qty_formula_id.execute(
                    consumption=consumption,
                    previous_reading=self.previous_reading,
                    current_reading=self.current_reading,
                    template=template,
                    account=account,
                    category=category,
                    line=line,
                )
            elif template and template.discount_formula_id:
                discount_units, name = template.discount_formula_id.execute(
                    consumption=consumption,
                    previous_reading=self.previous_reading,
                    current_reading=self.current_reading,
                    template=template,
                    account=account,
                    category=category,
                    line=line,
                )

            discount_units = max(discount_units or 0.0, 0.0)
            sponsor_id = template.sponsor_id.id if template and template.sponsor_id else False
            if discount_units > 0 and line.specific_price:
                qty = discount_units
                price = -abs(line.specific_price)
            else:
                qty = 1.0
                price = 0.0

        return qty, price, name, product_id, sponsor_id

    def _accumulate_amount(self, meter_line_type, amount):
        if meter_line_type == 'consumption':
            self.amount_energy += amount
        elif meter_line_type in ('fixed_fee', 'service_charge'):
            self.amount_service += amount
        elif meter_line_type in ('local_fee', 'mu_allim', 'cleaning', 'municipality'):
            self.amount_local_fee += amount
        elif meter_line_type == 'discount':
            # الخصومات: البند سالب في الفاتورة لكن الحقل يُخزّن القيمة الموجبة
            self.amount_discount += abs(amount)

    @api.model
    def cron_update_overdue_orders(self):
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'utility.billing_batch_size', 1000))
        self.search([
            ('bill_state', 'not in', ('paid', 'cancelled', 'overdue')),
            ('date_order', '<', date.today()),
            ('balance_due', '>', 0),
        ], limit=batch_size)._compute_bill_state()

    @api.model
    def cron_send_due_reminders(self):
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'utility.reminder_batch_size', 500))
        orders = self.search([
            ('bill_state', '=', 'overdue'),
            ('balance_due', '>', 0),
            ('customer_id', '!=', False),
        ], limit=batch_size, order='date_order asc, id asc')
        orders._create_overdue_notifications()
        return len(orders)




class UtilitySaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    _description = 'بند فاتورة كهرباء'

    contract_id = fields.Many2one(
        'account.analytic.account',
        string='عقد الاشتراك',
    )
    sponsor_id = fields.Many2one(
        'res.partner',
        string='الجهة الداعمة',
    )
    meter_line_type = fields.Selection([
        ('consumption', 'استهلاك'),
        ('service_charge', 'رسم خدمة ثابت'),
        ('fixed_fee', 'رسم ثابت (قديم)'),
        ('mu_allim', 'رسم المعلم'),
        ('cleaning', 'رسم النظافة'),
        ('municipality', 'رسم المجلس المحلي'),
        ('discount', 'خصم'),
        ('penalty', 'غرامة'),
        ('other', 'أخرى'),
    ], string='نوع البند')

    def _get_company_config(self, company_field, config_key):
        company = self.company_id or self.env.company
        val = company[company_field] if hasattr(company, company_field) else False
        if val:
            return val.id if hasattr(val, 'id') else val
        return int(self.env['ir.config_parameter'].sudo().get_param(config_key, 0))

    def _prepare_invoice_line(self, **optional_values):
        res = super(UtilitySaleOrderLine, self)._prepare_invoice_line(**optional_values)
        if self.sponsor_id:
            res['partner_id'] = self.sponsor_id.id

        acc_id = False
        product_id = False
        company = self.company_id or self.env.company
        order = self.order_id

        if self.meter_line_type == 'consumption':
            if order and order.customer_id:
                subscriber = order.customer_id.subscriber_id
                if subscriber and subscriber.revenue_account_id:
                    acc_id = subscriber.revenue_account_id.id

        elif self.meter_line_type in ('service_charge', 'fixed_fee'):
            if hasattr(company, 'fixed_fee_product_id') and company.fixed_fee_product_id:
                product_id = company.fixed_fee_product_id.id
            acc_id = self._get_company_config('fixed_fee_account_id', 'utility.fixed_fee_account_id')

        elif self.meter_line_type == 'mu_allim':
            if hasattr(company, 'mu_allim_product_id') and company.mu_allim_product_id:
                product_id = company.mu_allim_product_id.id
            acc_id = self._get_company_config('mu_allim_account_id', 'utility.mu_allim_account_id')

        elif self.meter_line_type == 'cleaning':
            if hasattr(company, 'cleaning_product_id') and company.cleaning_product_id:
                product_id = company.cleaning_product_id.id
            acc_id = self._get_company_config('cleaning_account_id', 'utility.cleaning_account_id')

        elif self.meter_line_type == 'municipality':
            if hasattr(company, 'local_fee_product_id') and company.local_fee_product_id:
                product_id = company.local_fee_product_id.id
            acc_id = self._get_company_config('local_fee_account_id', 'utility.local_fee_account_id')

        elif self.meter_line_type == 'discount':
            if hasattr(company, 'discount_product_id') and company.discount_product_id:
                product_id = company.discount_product_id.id
            acc_id = self._get_company_config('discount_account_id', 'utility.discount_account_id')

        elif self.meter_line_type == 'penalty':
            if hasattr(company, 'penalty_product_id') and company.penalty_product_id:
                product_id = company.penalty_product_id.id
            acc_id = self._get_company_config('fine_account_id', 'utility.fine_account_id')

        if not product_id and self.product_id:
            product_id = self.product_id.id
        if product_id:
            res['product_id'] = product_id

        if acc_id:
            res['account_id'] = acc_id

        # Fallback if account_id is missing or False to satisfy database constraint
        if not res.get('account_id'):
            target_prod = self.env['product.product'].browse(res.get('product_id')) if res.get('product_id') else self.product_id
            if target_prod:
                income_acc = target_prod.property_account_income_id or target_prod.categ_id.property_account_income_categ_id
                if income_acc:
                    res['account_id'] = income_acc.id

        if not res.get('account_id'):
            journal = self.env['account.journal'].search([
                ('type', '=', 'sale'), ('company_id', '=', company.id)
            ], limit=1)
            if journal and journal.default_account_id:
                res['account_id'] = journal.default_account_id.id
            else:
                fallback_acc = self.env['account.account'].search([
                    ('company_id', '=', company.id),
                    ('account_type', 'in', ('income', 'income_other')),
                    ('deprecated', '=', False)
                ], limit=1)
                if not fallback_acc:
                    fallback_acc = self.env['account.account'].search([
                        ('company_id', '=', company.id),
                        ('deprecated', '=', False)
                    ], limit=1)
                if fallback_acc:
                    res['account_id'] = fallback_acc.id

        return res



class UtilityAccountMove(models.Model):
    _inherit = 'account.move'

    workflow_process_id = fields.Many2one('sale.workflow.process', string='مسار العمل التلقائي')
    sale_type_id = fields.Many2one('sale.order.type', string='نوع أمر البيع')
    previous_reading = fields.Float('القراءة السابقة')
    current_reading = fields.Float('القراءة الحالية')
    consumption = fields.Float('الاستهلاك')

    def _post(self, soft=True):
        res = super(UtilityAccountMove, self)._post(soft=soft)
        for move in self:
            for line in move.line_ids:
                if line.sale_line_ids and line.sale_line_ids[0].sponsor_id:
                    if line.partner_id != line.sale_line_ids[0].sponsor_id:
                        line.write({'partner_id': line.sale_line_ids[0].sponsor_id.id})
        return res
