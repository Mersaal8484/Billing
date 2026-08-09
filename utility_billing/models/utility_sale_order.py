from datetime import date
from urllib.parse import quote
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilitySaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'utility.dropdown.mixin']
    effective_date = fields.Date(string='تاريخ الفعالية', copy=False)
    commitment_date = fields.Datetime(string='تاريخ الالتزام', copy=False)
    expected_date = fields.Datetime(string='التاريخ المتوقع', copy=False)
    picking_policy = fields.Selection([
        ('direct', 'تسليم كل منتج عند توفره'),
        ('one', 'تسليم جميع المنتجات دفعة واحدة'),
    ], string='سياسة الشحن')
    incoterm = fields.Many2one('account.incoterms', string='الإنكوتيرمز')
    incoterm_location = fields.Char(string='موقع الإنكوتيرم')
    warehouse_id = fields.Many2one('stock.warehouse', string='المستودع')
    delivery_count = fields.Integer(string='عدد الشحنات')

    customer_id = fields.Many2one('utility.customer', 'الحساب', index=True)
    meter_id = fields.Many2one('utility.meter', 'العداد', index=True)
    reading_id = fields.Many2one('utility.reading', 'قراءة العداد', index=True, ondelete='restrict')
    reading_component_ids = fields.One2many(
        'utility.bill.reading.component', 'sale_order_id',
        string='مكونات استهلاك الفاتورة', copy=False, readonly=True)
    reading_component_count = fields.Integer(
        'عدد مقاطع القراءة', compute='_compute_reading_component_count')
    available_billing_period_ids = fields.Many2many('date.range', compute='_compute_available_billing_period_ids')
    date_range_id = fields.Many2one('date.range', 'فترة الفاتورة', index=True, required=True)
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

    @api.constrains('customer_id', 'partner_id')
    def _check_utility_accounting_partner(self):
        for order in self.filtered('customer_id'):
            expected = order.customer_id.partner_id
            if order.partner_id != expected:
                raise ValidationError(_(
                    'شريك أمر البيع %s لا يطابق الشريك المحاسبي للحساب الكهربائي %s.'
                ) % (order.partner_id.display_name, expected.display_name))

    amount_energy = fields.Monetary('قيمة الطاقة', currency_field='currency_id')
    amount_service = fields.Monetary('رسم الخدمة الثابت', currency_field='currency_id')
    amount_discount = fields.Monetary('الخصومات', currency_field='currency_id')
    amount_local_fee = fields.Monetary('الرسوم المحلية', currency_field='currency_id')
    amount_penalty = fields.Monetary('الغرامات', compute='_compute_amount_penalty', store=True, currency_field='currency_id')
    penalty_ids = fields.One2many('utility.penalty', 'sale_order_id', string='سجل الغرامات')
    utility_move_ids = fields.One2many(
        'account.move', 'utility_sale_order_id', string='فواتير الكهرباء المحاسبية')

    qr_code_value = fields.Char('بيانات QR', compute='_compute_qr_code', readonly=True)
    qr_code_url = fields.Char('رابط QR', compute='_compute_qr_code', readonly=True)
    disconnection_order_id = fields.Many2one('utility.service.order', string='أمر الفصل', readonly=True, copy=False)
    reconnection_order_id = fields.Many2one('utility.service.order', string='أمر إعادة الخدمة', readonly=True, copy=False)

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
        for order in self:
            billing_period = order.customer_id._get_effective_billing_period() if order.customer_id else False
            region_id = order.customer_id.region_id.id if order.customer_id and order.customer_id.region_id else False
            domain = self._get_open_period_domain(
                work_type='readings', billing_period=billing_period, region_id=region_id)
            order.available_billing_period_ids = self.env['date.range'].search(domain)

    @api.onchange('customer_id')
    def _onchange_customer_id_date_range(self):
        available_periods = self.available_billing_period_ids
        if self.date_range_id and self.date_range_id not in available_periods:
            self.date_range_id = False
        if not self.date_range_id and len(available_periods) == 1:
            self.date_range_id = available_periods.id
        return {'domain': {'date_range_id': [('id', 'in', available_periods.ids)]}}

    @api.constrains('customer_id', 'date_range_id', 'reading_id', 'period_start', 'period_end')
    def _check_billing_period_matches_customer(self):
        for order in self.filtered(lambda item: item.customer_id and item.date_range_id):
            expected = order.customer_id._get_effective_billing_period()
            if expected == 'biweekly':
                expected = 'semi_monthly'

            period = order.date_range_id
            if period.period_role != 'reading':
                raise ValidationError(_('فترة الفاتورة يجب أن تكون من نوع قراءات، وليست فترة تحصيل.'))
            if expected and period.billing_cadence != expected:
                raise ValidationError(_(
                    'دورية الفترة المختارة (%s) لا تطابق دورية المشترك (%s).')
                    % (period.billing_cadence, expected))
            if order.reading_id and order.reading_id.date_range_id != period:
                raise ValidationError(_(
                    'فترة الفاتورة يجب أن تطابق فترة القراءة المرتبطة حرفياً.'))

            # التحقق من منع الفواتير المكررة لنفس المشترك والفترة
            duplicate = self.search([
                ('customer_id', '=', order.customer_id.id),
                ('date_range_id', '=', order.date_range_id.id),
                ('state', '!=', 'cancel'),
                ('id', '!=', order.id)
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'توجد فاتورة أخرى منشأة بالفعل للمشترك [%s] في الفترة [%s] (رقم الفاتورة: %s).'
                ) % (order.customer_id.display_name, period.name, duplicate.name))

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

    @api.depends('partner_id', 'customer_id', 'invoice_ids.state', 'utility_move_ids.state')
    def _compute_previous_balance(self):
        for order in self:
            if not order.customer_id:
                order.previous_balance = 0.0
                continue
            posted_moves = (order.invoice_ids | order.utility_move_ids).filtered(
                lambda move: move.state == 'posted')
            order.previous_balance = order.customer_id._get_receivable_balance(
                exclude_move_ids=posted_moves.ids)

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
            customer_id = vals.get('customer_id')
            if customer_id:
                customer = self.env['utility.customer'].browse(customer_id).exists()
                if not customer:
                    raise ValidationError(_('الحساب الكهربائي المحدد غير موجود.'))
                expected_partner_id = customer.partner_id.id
                if vals.get('partner_id') and vals['partner_id'] != expected_partner_id:
                    raise ValidationError(_('شريك أمر البيع يجب أن يطابق شريك الحساب الكهربائي.'))
                vals['partner_id'] = expected_partner_id
            if vals.get('name', '/') == '/' and vals.get('type_id'):
                sale_type = self.env['sale.order.type'].browse(vals['type_id'])
                if sale_type.sequence_id:
                    vals['name'] = sale_type.sequence_id.next_by_id()
        return super(UtilitySaleOrder, self).create(vals_list)

    def action_confirm(self):
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

        if contracts_to_create:
            contracts = self.env['account.analytic.account'].create(contracts_to_create)
            for line, contract in zip(lines_mapping, contracts):
                line.contract_id = contract.id
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

    def _create_overdue_notifications(self):
        self._create_notification_logs(
            'bill_overdue',
            lambda order: _('الفاتورة %s متأخرة وبها مبلغ مستحق %.2f. يرجى السداد لتجنب الفصل.')
                          % (order.name, order.balance_due),
            sms_config_key='utility.send_sms_on_overdue',
            subject=_('تنبيه فاتورة متأخرة'),
        )

    BILL_PROTECTED_FIELDS = frozenset({
        'customer_id', 'meter_id', 'reading_id', 'date_range_id',
        'period_start', 'period_end', 'previous_reading', 'current_reading',
        'consumption', 'contract_template_id', 'order_line',
        'amount_energy', 'amount_service', 'amount_discount',
        'amount_local_fee', 'amount_penalty',
    })

    def write(self, vals):
        if 'customer_id' in vals or 'partner_id' in vals:
            for order in self:
                customer = self.env['utility.customer'].browse(
                    vals.get('customer_id', order.customer_id.id)).exists()
                if customer:
                    expected_partner_id = customer.partner_id.id
                    if vals.get('partner_id', expected_partner_id) != expected_partner_id:
                        raise ValidationError(_('شريك أمر البيع يجب أن يطابق شريك الحساب الكهربائي.'))
                    vals['partner_id'] = expected_partner_id
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


class UtilitySaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    _description = 'بند فاتورة كهرباء'

    virtual_available_at_date = fields.Float(string='الكمية الافتراضية المتاحة في التاريخ', copy=False)
    forecast_expected_date = fields.Datetime(string='تاريخ التوقع المتوقع', copy=False)
    forecast_is_date_exceeded = fields.Boolean(string='تم تجاوز التاريخ المتوقع')
    scheduled_date = fields.Datetime(string='التاريخ المجدول', copy=False)
    qty_available_today = fields.Float(string='الكمية المتاحة اليوم', copy=False)
    free_qty_today = fields.Float(string='الكمية الحرة اليوم', copy=False)
    qty_to_deliver = fields.Float(string='الكمية المتبقية للتسليم', copy=False)
    is_mto = fields.Boolean(string='إنتاج حسب الطلب')
    display_qty_widget = fields.Boolean(string='عرض أداة الكمية')

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

    @api.depends(
        'qty_invoiced', 'qty_delivered', 'product_uom_qty', 'state',
        'order_id.customer_id', 'order_id.reading_id',
    )
    def _compute_qty_to_invoice(self):
        """Make utility billing lines invoiceable from ordered quantities.

        Electricity billing services are not delivered through stock pickings.
        Their invoiceability must therefore not depend on the product's
        delivery-based invoice policy, including for products configured before
        the utility product defaults were corrected.
        """
        super()._compute_qty_to_invoice()
        utility_lines = self.filtered(
            lambda line: line.order_id.customer_id and not line.display_type
        )
        for line in utility_lines:
            if line.state in ('sale', 'done'):
                line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced

    def _get_company_config(self, company_field, config_key):
        company = self.company_id or self.env.company
        val = company[company_field] if hasattr(company, company_field) else False
        if val:
            return val.id if hasattr(val, 'id') else val
        return int(self.env['ir.config_parameter'].sudo().get_param(config_key, 0))

    def _prepare_invoice_line(self, **optional_values):
        res = super(UtilitySaleOrderLine, self)._prepare_invoice_line(**optional_values)
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
