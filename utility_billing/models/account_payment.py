from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    utility_sale_order_id = fields.Many2one('sale.order', string='فاتورة الكهرباء', index=True)
    utility_customer_id = fields.Many2one(
        'utility.customer', related='utility_sale_order_id.customer_id',
        string='حساب الكهرباء', store=True, index=True, readonly=True)
    utility_invoice_id = fields.Many2one(
        'account.move', string='الفاتورة المحاسبية المحددة', index=True,
        copy=False, domain="[('utility_sale_order_id', '=', utility_sale_order_id), ('state', '=', 'posted')]",
        help='الفاتورة الوحيدة التي ستتم مطابقة هذه الدفعة معها.')
    service_charge_id = fields.Many2one('utility.service.charge', string='رسم الخدمة', index=True, copy=False, check_company=True)
    utility_payment_method = fields.Selection([
        ('cash', 'نقدي (تحصيل ميداني)'),
        ('bank', 'بنكي (تحصيل ميداني / تحويل)'),
        ('electronic', 'إلكتروني (بوابة دفع / محفظة)'),
    ], string='طريقة دفع الكهرباء', default='cash')
    electronic_doc_no = fields.Char(string='رقم المستند الإلكتروني')
    is_invoice_verified = fields.Boolean(string='تم التحقق من الفاتورة')
    date_range_id = fields.Many2one(
        'date.range',
        string='فترة الدفع',
        domain="[('period_role', '=', 'payment')]",
    )
    timing_classification = fields.Selection([
        ('on_time', 'في الموعد المحدد'),
        ('late', 'متأخر'),
        ('exceptional', 'استثنائي'),
        ('outside_window', 'خارج نافذة التحصيل الميداني'),
    ], string='تصنيف توقيت السداد', default='on_time', index=True)
    qr_code_value = fields.Char('بيانات QR', compute='_compute_utility_qr_code', readonly=True)
    qr_code_url = fields.Char('رابط QR', compute='_compute_utility_qr_code', readonly=True)
    allocation_ids = fields.One2many(
        'utility.payment.allocation', 'payment_id', string='تخصيصات الدفعة',
        readonly=True, copy=False)
    allocation_count = fields.Integer(
        'عدد التخصيصات', compute='_compute_allocation_count')

    @api.depends('allocation_ids')
    def _compute_allocation_count(self):
        for payment in self:
            payment.allocation_count = len(payment.allocation_ids)

    def action_view_utility_allocations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('تخصيصات الدفعة'),
            'res_model': 'utility.payment.allocation',
            'view_mode': 'tree,form',
            'domain': [('payment_id', '=', self.id)],
            'context': {'default_payment_id': self.id, 'create': False},
        }

    @api.onchange('utility_payment_method')
    def _onchange_utility_payment_method(self):
        if self.utility_payment_method in ('cash', 'bank'):
            user_journal = self.env.user.collection_journal_id
            if user_journal and user_journal.company_id == self.company_id:
                self.journal_id = user_journal
        elif self.utility_payment_method == 'electronic':
            provider = self.env['utility.integration.provider'].search([
                ('company_id', '=', self.company_id.id),
                ('provider_type', 'in', ('payment_gateway', 'mobile_money')),
                ('active', '=', True),
            ], limit=1)
            if provider and provider.mode != 'manual':
                elec_journal = self.env['account.journal'].search([
                    ('company_id', '=', self.company_id.id),
                    ('type', '=', 'bank'),
                ], limit=1)
                if elec_journal:
                    self.journal_id = elec_journal

    @api.depends('name', 'amount', 'date', 'state', 'utility_sale_order_id', 'utility_sale_order_id.name', 'utility_sale_order_id.customer_id.customer_number', 'utility_sale_order_id.meter_id.meter_number', 'date_range_id.name')
    def _compute_utility_qr_code(self):
        for payment in self:
            order = payment.utility_sale_order_id
            payload = '|'.join([
                'UTILITY-PAYMENT',
                payment.company_id.name or '',
                payment.name or '',
                order.name or '',
                order.customer_id.customer_number or '',
                order.partner_id.name or payment.partner_id.name or '',
                order.meter_id.meter_number or '',
                payment.date_range_id.name or '',
                'amount=%.2f' % (payment.amount or 0.0),
                'date=%s' % (payment.date or ''),
                'state=%s' % (payment.state or ''),
            ])
            payment.qr_code_value = payload
            payment.qr_code_url = '/report/barcode/?barcode_type=QR&value=%s' % quote(payload)

    def _get_payment_period_for_order(self, order):
        """Return only the payment period directly linked to the bill period via reading_period_id."""
        if not order or not order.date_range_id:
            return self.env['date.range']

        # 1. البحث باستخدام الرابط المباشر الصريح reading_period_id
        period = self.env['date.range'].search([
            ('period_role', '=', 'payment'),
            ('reading_period_id', '=', order.date_range_id.id),
            ('company_id', 'in', [order.company_id.id, False]),
        ], order='is_current_period desc, date_start desc, id desc', limit=1)

        # 2. التوافق العكسي: البحث بـ parent_id إذا لم يتوفر reading_period_id
        if not period:
            period = self.env['date.range'].search([
                ('period_role', '=', 'payment'),
                ('parent_id', '=', order.date_range_id.id),
                ('company_id', 'in', [order.company_id.id, False]),
            ], order='is_current_period desc, date_start desc, id desc', limit=1)

        return period

    def _validate_utility_payment_period(self):
        """Ensure a utility payment belongs to the bill's exact reading period."""
        for payment in self.filtered('utility_sale_order_id'):
            order_period = payment.utility_sale_order_id.date_range_id
            if not order_period:
                raise ValidationError(_('لا يمكن تسجيل التحصيل لأن الفاتورة غير مرتبطة بفترة قراءة.'))
            if not payment.date_range_id:
                raise ValidationError(_('لا توجد فترة دفع مرتبطة بفترة قراءة الفاتورة "%s".') % order_period.display_name)
            if payment.date_range_id.period_role != 'payment':
                raise ValidationError(_('فترة التحصيل يجب أن تكون من نوع سداد وتحصيل.'))
            linked_reading_period = payment.date_range_id.reading_period_id or payment.date_range_id.parent_id
            if linked_reading_period != order_period:
                raise ValidationError(_('فترة التحصيل يجب أن تكون فترة الدفع المرتبطة مباشرة بفترة قراءة الفاتورة "%s".') % order_period.display_name)

    def _validate_utility_payment_amount(self):
        """Validate and lock the exact utility invoice before posting payment."""
        self.ensure_one()
        order = self.utility_sale_order_id
        if not order:
            return
        if self.payment_type != 'inbound':
            raise ValidationError(_(
                'الدفعات الصادرة لا تستخدم مسار تحصيل فواتير الكهرباء.'
            ))
        invoice = self.utility_invoice_id
        if (not invoice or invoice.utility_sale_order_id != order
                or invoice.partner_id != order.customer_id.partner_id
                or invoice.move_type != 'out_invoice'):
            raise ValidationError(_('يجب تحديد فاتورة كهرباء مدينة صحيحة للدفع.'))
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT id FROM account_move WHERE id = %s FOR UPDATE',
            [invoice.id],
        )
        invoice.invalidate_cache([
            'state', 'partner_id', 'move_type', 'amount_residual', 'payment_state'])
        if invoice.state != 'posted':
            raise ValidationError(_('لا يمكن الدفع إلا لفاتورة محاسبية مرحلة.'))
        if self.amount > invoice.amount_residual:
            raise ValidationError(_(
                'مبلغ الدفعة %.2f يتجاوز المتبقي %.2f في الفاتورة المحددة.'
            ) % (self.amount, invoice.amount_residual))

    @api.onchange('utility_sale_order_id')
    def _onchange_utility_sale_order_id(self):
        if self.utility_sale_order_id:
            payment_period = self._get_payment_period_for_order(self.utility_sale_order_id)
            self.date_range_id = payment_period

    @api.constrains('utility_sale_order_id', 'utility_invoice_id', 'partner_id', 'date_range_id')
    def _check_utility_payment_period_matches_bill(self):
        self._validate_utility_payment_period()
        for payment in self.filtered('utility_sale_order_id'):
            order = payment.utility_sale_order_id
            expected_partner = order.customer_id.partner_id
            if payment.partner_id != expected_partner:
                raise ValidationError(_('شريك الدفعة يجب أن يطابق شريك الحساب الكهربائي.'))
            if not payment.utility_invoice_id:
                raise ValidationError(_('يجب تحديد الفاتورة المحاسبية التي ستطابق معها الدفعة.'))
            if payment.utility_invoice_id.utility_sale_order_id != order:
                raise ValidationError(_('الفاتورة المحددة لا تخص فاتورة الكهرباء المختارة.'))
            if payment.utility_invoice_id.partner_id != expected_partner:
                raise ValidationError(_('شريك الفاتورة المحاسبية لا يطابق شريك الحساب الكهربائي.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order_id = vals.get('utility_sale_order_id')
            if order_id:
                order = self.env['sale.order'].browse(order_id)
                if not order.customer_id:
                    raise ValidationError(_('فاتورة الكهرباء لا تحتوي على حساب كهربائي.'))
                expected_partner_id = order.customer_id.partner_id.id
                if vals.get('partner_id') and vals['partner_id'] != expected_partner_id:
                    raise ValidationError(_('شريك الدفعة يجب أن يطابق شريك الحساب الكهربائي.'))
                vals['partner_id'] = expected_partner_id
                payment_period = self._get_payment_period_for_order(order)
                if not payment_period:
                    raise ValidationError(
                        _('لا توجد فترة دفع مرتبطة بفترة قراءة الفاتورة "%s".')
                        % order.date_range_id.display_name
                    )
                vals['date_range_id'] = payment_period.id

            # توجيه اليومية تلقائياً إذا كان الدفع يدوياً ولم تتحدد اليومية
            payment_method = vals.get('utility_payment_method', 'cash')
            if payment_method in ('cash', 'bank') and not vals.get('journal_id'):
                user_journal = self.env.user.collection_journal_id
                if user_journal:
                    vals['journal_id'] = user_journal.id

        payments = super().create(vals_list)
        for payment, vals in zip(payments, vals_list):
            if vals.get('service_charge_id'):
                payment.service_charge_id.payment_id = payment.id
        return payments

    def write(self, vals):
        if vals.get('utility_sale_order_id'):
            order = self.env['sale.order'].browse(vals['utility_sale_order_id'])
            expected_partner_id = order.customer_id.partner_id.id
            if vals.get('partner_id', expected_partner_id) != expected_partner_id:
                raise ValidationError(_('شريك الدفعة يجب أن يطابق شريك الحساب الكهربائي.'))
            vals['partner_id'] = expected_partner_id
            payment_period = self._get_payment_period_for_order(order)
            if not payment_period:
                raise ValidationError(
                    _('لا توجد فترة دفع مرتبطة بفترة قراءة الفاتورة "%s".')
                    % order.date_range_id.display_name
                )
            vals['date_range_id'] = payment_period.id
        res = super().write(vals)
        if vals.get('service_charge_id'):
            for payment in self:
                payment.service_charge_id.payment_id = payment.id
        return res

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        order_id = self.env.context.get('default_utility_sale_order_id')
        if order_id and 'date_range_id' in fields_list:
            order = self.env['sale.order'].browse(order_id).exists()
            payment_period = self._get_payment_period_for_order(order)
            if payment_period:
                res['date_range_id'] = payment_period.id
        if order_id and 'utility_invoice_id' in fields_list:
            order = self.env['sale.order'].browse(order_id).exists()
            if order:
                posted_moves = (order.invoice_ids | order.utility_move_ids).filtered(
                    lambda move: move.state == 'posted' and move.move_type in ('out_invoice', 'out_refund'))
                if len(posted_moves) == 1:
                    res['utility_invoice_id'] = posted_moves.id

        # تعيين طريقة الدفع الافتراضية واليومية الميدانية للمستخدم
        if 'utility_payment_method' in fields_list and not res.get('utility_payment_method'):
            res['utility_payment_method'] = 'cash'

        if 'journal_id' in fields_list and not res.get('journal_id'):
            if self.env.user.collection_journal_id:
                res['journal_id'] = self.env.user.collection_journal_id.id
        return res

    def _create_payment_notification(self):
        Notification = self.env['utility.notification.log'].sudo()
        send_sms = self.env['ir.config_parameter'].sudo().get_param('utility.send_sms_on_payment', False)
        for payment in self.filtered('utility_sale_order_id'):
            order = payment.utility_sale_order_id
            body = _('تم استلام دفعة بمبلغ %.2f للفاتورة %s. المتبقي %.2f.') % (
                payment.amount, order.name, order.balance_due)
            Notification.create_log(
                'payment_received', body, record=payment, customer=order.customer_id,
                partner=payment.partner_id, channel='portal', subject=_('استلام دفعة كهرباء'))
            if send_sms:
                Notification.create_log(
                    'payment_received', body, record=payment, customer=order.customer_id,
                    partner=payment.partner_id, channel='sms', subject=_('استلام دفعة كهرباء'))
    def action_post(self):
        # FIX-15: منع ترحيل دفعة على فاتورة ملغاة أو مدفوعة بالكامل
        for payment in self.filtered('utility_sale_order_id'):
            order = payment.utility_sale_order_id
            if not payment.date_range_id:
                payment_period = payment._get_payment_period_for_order(order)
                if payment_period:
                    payment.date_range_id = payment_period.id
                else:
                    raise ValidationError(_('لا توجد فترة دفع مرتبطة بفترة قراءة هذه الفاتورة.'))
            payment._validate_utility_payment_period()
            payment._validate_utility_payment_amount()
            if order.state == 'cancel':
                raise ValidationError(
                    'لا يمكن تسجيل دفعة على فاتورة ملغاة [%s]. يُرجى التحقق من رقم الفاتورة.' % order.name
                )
            if order.bill_state == 'paid' and order.balance_due <= 0:
                raise ValidationError(
                    'الفاتورة [%s] مدفوعة بالكامل بالفعل. لا حاجة لتسجيل دفعة إضافية.' % order.name
                )
            # تحديد تصنيف توقيت السداد
            period = payment.date_range_id
            pay_datetime = fields.Datetime.to_datetime(payment.date) or fields.Datetime.now()
            if period and period.payment_window_start and period.payment_window_end:
                if period.payment_window_start <= pay_datetime <= period.payment_window_end:
                    payment.timing_classification = 'on_time'
                else:
                    payment.timing_classification = 'late' if pay_datetime > period.payment_window_end else 'outside_window'
            elif period and period.state in ('open', 'payment_open'):
                payment.timing_classification = 'on_time'
            else:
                payment.timing_classification = 'late'
        res = super().action_post()
        utility_payments = self.filtered('utility_customer_id')
        for payment in utility_payments:
            if payment.move_id and 'utility_customer_id' in payment.move_id._fields:
                payment.move_id.write({'utility_customer_id': payment.utility_customer_id.id})
        self.filtered('service_charge_id').mapped('service_charge_id').action_mark_paid_from_payment()
        for payment in self.filtered('utility_sale_order_id'):
            self.env['utility.payment.allocation'].with_context(
                utility_payment_source=(
                    'gateway' if payment.utility_payment_method == 'electronic'
                    else 'bank' if payment.utility_payment_method == 'bank'
                    else 'cashier'
                )
            ).allocate_payment(payment)
        self.filtered('utility_sale_order_id')._create_payment_notification()
        return res

    def _reconcile_utility_sale_order(self):
        """Backward-compatible entry point delegating to the single allocator."""
        self.ensure_one()
        return self.env['utility.payment.allocation'].allocate_payment(self)

