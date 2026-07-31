from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    utility_sale_order_id = fields.Many2one('sale.order', string='فاتورة الكهرباء', index=True)
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
        domain="[('work_type', '=', 'payment')]",
    )
    qr_code_value = fields.Char('بيانات QR', compute='_compute_utility_qr_code', readonly=True)
    qr_code_url = fields.Char('رابط QR', compute='_compute_utility_qr_code', readonly=True)

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
        """Return only the payment period directly linked to the bill period."""
        if not order or not order.date_range_id:
            return self.env['date.range']

        return self.env['date.range'].search([
            ('work_type', '=', 'payment'),
            ('parent_id', '=', order.date_range_id.id),
            ('company_id', 'in', [order.company_id.id, False]),
        ], order='is_current_period desc, date_start desc, id desc', limit=1)

    def _validate_utility_payment_period(self):
        """Ensure a utility payment belongs to the bill's exact reading period."""
        for payment in self.filtered('utility_sale_order_id'):
            order_period = payment.utility_sale_order_id.date_range_id
            if not order_period:
                raise ValidationError(_('لا يمكن تسجيل التحصيل لأن الفاتورة غير مرتبطة بفترة قراءة.'))
            if not payment.date_range_id:
                raise ValidationError(_('لا توجد فترة دفع مرتبطة بفترة قراءة الفاتورة "%s".') % order_period.display_name)
            if (
                payment.date_range_id.work_type != 'payment'
                or payment.date_range_id.parent_id != order_period
            ):
                raise ValidationError(_('فترة التحصيل يجب أن تكون فترة الدفع المرتبطة مباشرة بفترة قراءة الفاتورة "%s".') % order_period.display_name)

    @api.onchange('utility_sale_order_id')
    def _onchange_utility_sale_order_id(self):
        if self.utility_sale_order_id:
            payment_period = self._get_payment_period_for_order(self.utility_sale_order_id)
            self.date_range_id = payment_period

    @api.constrains('utility_sale_order_id', 'date_range_id')
    def _check_utility_payment_period_matches_bill(self):
        self._validate_utility_payment_period()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order_id = vals.get('utility_sale_order_id')
            if order_id:
                order = self.env['sale.order'].browse(order_id)
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
            if order.state == 'cancel':
                raise ValidationError(
                    'لا يمكن تسجيل دفعة على فاتورة ملغاة [%s]. يُرجى التحقق من رقم الفاتورة.' % order.name
                )
            if order.bill_state == 'paid' and order.balance_due <= 0:
                raise ValidationError(
                    'الفاتورة [%s] مدفوعة بالكامل بالفعل. لا حاجة لتسجيل دفعة إضافية.' % order.name
                )
        res = super().action_post()
        self.filtered('service_charge_id').mapped('service_charge_id').action_mark_paid_from_payment()
        for payment in self:
            payment._reconcile_utility_sale_order()
        self.filtered('utility_sale_order_id')._create_payment_notification()
        return res

    def _reconcile_utility_sale_order(self):
        self.ensure_one()
        if not self.move_id:
            return

        order = self.utility_sale_order_id
        invoices = self.env['account.move']
        if order:
            invoices |= (order.invoice_ids | order.utility_move_ids)

        if not invoices and self.partner_id:
            invoices = self.env['account.move'].search([
                ('partner_id', '=', self.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ('not_paid', 'partial', 'in_payment'))
            ])

        invoices = invoices.filtered(lambda m: m.state == 'posted' and m.payment_state in ('not_paid', 'partial', 'in_payment'))

        payment_lines = self.move_id.line_ids.filtered(
            lambda line: not line.reconciled and line.account_id.account_type == 'asset_receivable'
        )
        invoice_lines = invoices.mapped('line_ids').filtered(
            lambda line: not line.reconciled and line.account_id.account_type == 'asset_receivable'
        )
        lines = payment_lines | invoice_lines
        if len(lines) >= 2:
            lines.reconcile()

        # إجراء تسوية شاملة لحساب العملاء للشريك لضمان سداد الفاتورة تلقائياً
        if self.partner_id:
            partner_lines = self.env['account.move.line'].search([
                ('partner_id', '=', self.partner_id.id),
                ('reconciled', '=', False),
                ('account_id.account_type', '=', 'asset_receivable'),
                ('move_id.state', '=', 'posted')
            ])
            if len(partner_lines) >= 2:
                try:
                    partner_lines.reconcile()
                except Exception:
                    pass

