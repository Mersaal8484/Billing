from datetime import date, timedelta
from odoo import api, fields, models, _


class UtilitySaleOrder(models.Model):
    _inherit = 'sale.order'
    _description = 'Utility Bill (Sale Order)'

    customer_id = fields.Many2one('utility.customer', 'الحساب', index=True)
    meter_id = fields.Many2one('utility.meter', 'العداد')
    reading_id = fields.Many2one('utility.reading', 'قراءة العداد', index=True, ondelete='restrict')
    date_range_id = fields.Many2one('date.range', 'فترة الفوترة', index=True, required=True)

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

    amount_energy = fields.Float('قيمة الطاقة')
    amount_fixed = fields.Float('الرسم الثابت')
    amount_service = fields.Float('رسم الخدمة')
    amount_discount = fields.Float('الخصومات')
    amount_local_fee = fields.Float('الرسوم المحلية')
    amount_penalty = fields.Float('الغرامات')

    amount_paid = fields.Float('المدفوع', compute='_compute_payment', store=True)
    balance_due = fields.Float('المتبقي', compute='_compute_payment', store=True)
    is_overdue = fields.Boolean('متأخر', compute='_compute_payment', store=True)

    previous_balance = fields.Float('رصيد المتأخرات (سابق)', compute='_compute_previous_balance', store=True)
    total_due_amount = fields.Float('إجمالي المطلوب سداده (فاتورة + متأخرات)', compute='_compute_total_due_amount', store=True)

    bill_state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكدة'),
        ('sent', 'مرسلة'),
        ('paid', 'مدفوعة'),
        ('overdue', 'متأخرة'),
        ('cancelled', 'ملغاة'),
    ], string='حالة الفاتورة', default='draft', tracking=True, compute='_compute_bill_state', store=True)

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

    @api.depends('partner_id', 'state')
    def _compute_previous_balance(self):
        for order in self:
            if order.state == 'draft' and order.partner_id:
                # استخدام حقل credit القياسي من أودو والذي يمثل إجمالي الذمم المدينة (المتأخرات)
                order.previous_balance = order.partner_id.credit
            elif not order.partner_id:
                order.previous_balance = 0.0

    @api.depends('amount_total', 'previous_balance')
    def _compute_total_due_amount(self):
        for order in self:
            order.total_due_amount = order.amount_total + order.previous_balance

    def _prepare_invoice(self):
        res = super(UtilitySaleOrder, self)._prepare_invoice()
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

        return super(UtilitySaleOrder, self).action_confirm()

    def action_draft(self):
        res = super(UtilitySaleOrder, self).action_draft()
        for order in self:
            if order.reading_id and order.reading_id.state == 'billed':
                order.reading_id.state = 'under_review'
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

    @api.depends('amount_total', 'invoice_ids.state', 'invoice_ids.payment_state', 'invoice_ids.amount_residual', 'state', 'date_order')
    def _compute_payment(self):
        for r in self:
            posted_invoices = r.invoice_ids.filtered(lambda i: i.state == 'posted')
            paid = sum(posted_invoices.mapped(lambda i: i.amount_total - i.amount_residual))
            r.amount_paid = paid
            r.balance_due = r.amount_total - paid
            r.is_overdue = r.balance_due > 0 and r.date_order and r.date_order.date() < date.today()

    @api.depends('state', 'is_overdue', 'balance_due', 'invoice_ids.state', 'invoice_ids.payment_state')
    def _compute_bill_state(self):
        for r in self:
            if r.state == 'cancel':
                r.bill_state = 'cancelled'
            elif r.state == 'draft':
                r.bill_state = 'draft'
            else:
                posted_invoices = r.invoice_ids.filtered(lambda i: i.state == 'posted')
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

    def action_recalculate_bill(self):
        for order in self:
            if order.state == 'draft':
                order._calculate_amounts()

    def _calculate_amounts(self):
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
        self.amount_fixed = 0.0
        self.amount_service = 0.0
        self.amount_discount = 0.0
        self.amount_local_fee = 0.0
        self.amount_penalty = 0.0

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
                    'is_tax': False,
                    'sponsor_id': sponsor_id,
                    'meter_line_type': line.meter_line_type,
                }))
                self._accumulate_amount(line.meter_line_type, amount)

            # الرسوم المحلية التلقائية (المعلم، النظافة، المحلي) من القالب والإعدادات
            existing_local_fee_kinds = [l.local_fee_kind for l in template.line_ids if l.meter_line_type == 'local_fee']
            ICPSudo = self.env['ir.config_parameter'].sudo()

            if 'mu_allim' not in existing_local_fee_kinds and template.local_fee_mu_allim > 0:
                prod_id = int(ICPSudo.get_param('utility.mu_allim_product_id', 0))
                amount = consumption * template.local_fee_mu_allim
                if amount > 0:
                    lines.append((0, 0, {
                        'product_id': prod_id or False,
                        'name': 'رسم المعلم',
                        'product_uom_qty': consumption,
                        'price_unit': template.local_fee_mu_allim,
                        'is_tax': False,
                        'meter_line_type': 'local_fee',
                    }))
                    self.amount_local_fee += amount

            if 'cleaning' not in existing_local_fee_kinds and template.local_fee_cleaning > 0:
                prod_id = int(ICPSudo.get_param('utility.cleaning_product_id', 0))
                amount = consumption * template.local_fee_cleaning
                if amount > 0:
                    lines.append((0, 0, {
                        'product_id': prod_id or False,
                        'name': 'رسم النظافة',
                        'product_uom_qty': consumption,
                        'price_unit': template.local_fee_cleaning,
                        'is_tax': False,
                        'meter_line_type': 'local_fee',
                    }))
                    self.amount_local_fee += amount

            if 'municipality' not in existing_local_fee_kinds and template.local_fee_per_kwh > 0:
                prod_id = int(ICPSudo.get_param('utility.local_fee_product_id', 0))
                amount = consumption * template.local_fee_per_kwh
                if amount > 0:
                    lines.append((0, 0, {
                        'product_id': prod_id or False,
                        'name': 'رسم محلي (مجالس محلية)',
                        'product_uom_qty': consumption,
                        'price_unit': template.local_fee_per_kwh,
                        'is_tax': False,
                        'meter_line_type': 'local_fee',
                    }))
                    self.amount_local_fee += amount

        # ─────────────────────────────────────────────────────────────
        # حدود الفوترة (min/max) — تُطبَّق على الإجمالي قبل الخصم
        # ─────────────────────────────────────────────────────────────
        if template:
            pre_total = (self.amount_energy + self.amount_fixed
                         + self.amount_service + self.amount_local_fee)
            if template.min_charge and pre_total < template.min_charge:
                # إضافة بند فرق للحد الأدنى
                lines.append((0, 0, {
                    'product_id': fixed_product.id if fixed_product else False,
                    'name': f'تسوية إلى الحد الأدنى ({template.min_charge})',
                    'product_uom_qty': 1,
                    'price_unit': template.min_charge - pre_total,
                    'meter_line_type': 'fixed_fee',
                }))
                self.amount_fixed += template.min_charge - pre_total
            elif template.max_charge and pre_total > template.max_charge:
                # تخفيض إلى الحد الأقصى كبند خصم
                lines.append((0, 0, {
                    'product_id': fixed_product.id if fixed_product else False,
                    'name': f'تسوية إلى الحد الأقصى ({template.max_charge})',
                    'product_uom_qty': 1,
                    'price_unit': template.max_charge - pre_total,
                    'meter_line_type': 'discount',
                }))
                self.amount_discount += pre_total - template.max_charge

        self.order_line = [(5, 0, 0)] + lines

    def _compute_line_amounts(self, line, consumption, account, category, template):
        """حساب (qty, price, name, product_id, sponsor_id) لبند قالب عقد واحد."""
        qty = 0.0
        price = 0.0
        name = line.name or line.product_id.name or ''
        product_id = line.product_id.id if line.product_id else False
        sponsor_id = False

        # السعر من القالب (مصدر الحقيقة) — line.specific_price للـ override
        template_price = template.price_per_kwh if template else 0.0
        template_fixed = template.fixed_charge if template else 0.0
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

        elif line.meter_line_type == 'fixed_fee':
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
            price = line.specific_price or template_fixed

        elif line.meter_line_type == 'service_charge':
            qty = 1.0
            price = line.specific_price or template_service

        elif line.meter_line_type == 'local_fee':
            # الرسم المحلي = consumption × fee_per_kwh
            qty = consumption
            if line.specific_price:
                price = line.specific_price
            else:
                # اختيار السعر من الحقل المخصص على القالب حسب local_fee_kind
                if template:
                    if line.local_fee_kind == 'mu_allim':
                        price = template.local_fee_mu_allim
                    elif line.local_fee_kind == 'cleaning':
                        price = template.local_fee_cleaning
                    else:
                        price = template.local_fee_per_kwh
                else:
                    price = 0.0
            # تسمية افتراضية حسب النوع
            if not line.name:
                kind_labels = {
                    'municipality': 'رسم مجلس محلي',
                    'mu_allim': 'رسم المعلم',
                    'cleaning': 'رسم نظافة',
                    'other': 'رسم محلي',
                }
                name = kind_labels.get(line.local_fee_kind, 'رسم محلي')

        elif line.meter_line_type == 'discount':
            # خصم الدعم — أول N وحدة مدعومة
            if (category and getattr(category, 'subsidized_enabled', False) and consumption > 0):
                qty, price, name = category._get_subsidized_amount(consumption, template)
                price = -abs(price)
                sponsor_id = category.sponsor_id.id if hasattr(category, 'sponsor_id') and category.sponsor_id else False
            else:
                # حساب خصم قائم على discount_first_units في القالب
                if template and template.discount_first_units > 0 and consumption > 0:
                    units = min(consumption, template.discount_first_units)
                    qty = 1.0
                    price = -(units * (template.discount_unit_value or 0.0))
                else:
                    qty = 1.0
                    price = -(line.specific_price or 0.0)
                sponsor_id = template.sponsor_id.id if template and template.sponsor_id else False

        return qty, price, name, product_id, sponsor_id

    def _accumulate_amount(self, meter_line_type, amount):
        """تجميع المبلغ في الخانة المناسبة حسب نوع البند."""
        if meter_line_type == 'consumption':
            self.amount_energy += amount
        elif meter_line_type == 'fixed_fee':
            self.amount_fixed += amount
        elif meter_line_type == 'service_charge':
            self.amount_service += amount
        elif meter_line_type == 'local_fee':
            self.amount_local_fee += amount
        elif meter_line_type == 'discount':
            self.amount_discount += amount

    @api.model
    def cron_update_overdue_orders(self):
        today = date.today()
        orders = self.search([
            ('bill_state', 'not in', ('paid', 'cancelled', 'overdue')),
            ('date_order', '<', today),
            ('balance_due', '>', 0),
        ])
        orders.write({'bill_state': 'overdue'})

    @api.model
    def cron_send_due_reminders(self):
        pass


class UtilitySaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    _description = 'Utility Bill Line'

    is_tax = fields.Boolean('ضريبة', default=False)
    contract_id = fields.Many2one(
        'account.analytic.account',
        string='عقد الاشتراك',
    )
    sponsor_id = fields.Many2one(
        'res.partner',
        string='الجهة الداعمة (Sponsor)',
    )
    meter_line_type = fields.Selection([
        ('consumption', 'استهلاك'),
        ('fixed_fee', 'رسم ثابت'),
        ('service_charge', 'رسم خدمة'),
        ('local_fee', 'رسوم محلية'),
        ('discount', 'خصم'),
        ('penalty', 'غرامة'),
        ('other', 'أخرى'),
    ], string='نوع البند')

    def _prepare_invoice_line(self, **optional_values):
        res = super(UtilitySaleOrderLine, self)._prepare_invoice_line(**optional_values)
        if self.sponsor_id:
            res['partner_id'] = self.sponsor_id.id
            
        ICPSudo = self.env['ir.config_parameter'].sudo()
        acc_id = False
        
        if self.meter_line_type == 'discount':
            acc_id = int(ICPSudo.get_param('utility.discount_account_id', 0))
        elif self.meter_line_type == 'penalty':
            acc_id = int(ICPSudo.get_param('utility.fine_account_id', 0))
            
        if acc_id:
            res['account_id'] = acc_id
            
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
