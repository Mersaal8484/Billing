from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    utility_sale_order_id = fields.Many2one('sale.order', string='فاتورة الكهرباء', index=True)
    utility_payment_method = fields.Selection([
        ('cash', 'نقدي'),
        ('bank', 'بنكي'),
        ('electronic', 'إلكتروني'),
    ], string='طريقة دفع الكهرباء')
    electronic_doc_no = fields.Char(string='رقم المستند الإلكتروني')
    is_invoice_verified = fields.Boolean(string='تم التحقق من الفاتورة')
    cashier_shift_id = fields.Many2one('utility.cashier.shift', string='الوردية',
        default=lambda self: self._default_cashier_shift())
    collector_shift_id = fields.Many2one('utility.collector.shift', string='يومية التحصيل',
        default=lambda self: self._default_collector_shift())
    date_range_id = fields.Many2one('date.range', string='فترة الدفع',
        default=lambda self: self.env['date.range'].search([('is_current_period', '=', True), ('work_type', '=', 'payment')], limit=1))
    qr_code_value = fields.Char('بيانات QR', compute='_compute_utility_qr_code', readonly=True)
    qr_code_url = fields.Char('رابط QR', compute='_compute_utility_qr_code', readonly=True)


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
        if not order or not order.date_range_id:
            return self.env['date.range']
        payment_period = self.env['date.range'].search([
            ('work_type', '=', 'payment'),
            ('parent_id', '=', order.date_range_id.id),
            ('is_current_period', '=', True),
        ], limit=1)
        if not payment_period:
            payment_period = self.env['date.range'].search([
                ('work_type', '=', 'payment'),
                ('parent_id', '=', order.date_range_id.id),
            ], limit=1)
        return payment_period

    @api.onchange('utility_sale_order_id')
    def _onchange_utility_sale_order_id(self):
        if self.utility_sale_order_id:
            payment_period = self._get_payment_period_for_order(self.utility_sale_order_id)
            if payment_period:
                self.date_range_id = payment_period.id

    @api.constrains('utility_sale_order_id', 'date_range_id')
    def _check_utility_payment_period_matches_bill(self):
        for payment in self.filtered('utility_sale_order_id'):
            order_period = payment.utility_sale_order_id.date_range_id
            if not payment.date_range_id or not order_period:
                continue
            if payment.date_range_id.work_type != 'payment':
                raise ValidationError(_('فترة التحصيل يجب أن تكون من نوع دفع.'))
            if payment.date_range_id.parent_id != order_period:
                raise ValidationError(_('فترة التحصيل يجب أن تكون مرتبطة بفترة قراءة الفاتورة.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order_id = vals.get('utility_sale_order_id')
            if order_id:
                order = self.env['sale.order'].browse(order_id)
                payment_period = self._get_payment_period_for_order(order)
                if payment_period:
                    vals['date_range_id'] = payment_period.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('utility_sale_order_id'):
            order = self.env['sale.order'].browse(vals['utility_sale_order_id'])
            payment_period = self._get_payment_period_for_order(order)
            if payment_period:
                vals['date_range_id'] = payment_period.id
        return super().write(vals)

    @api.model
    def _default_cashier_shift(self):
        if self.env.context.get('cashier_shift_id'):
            return self.env.context['cashier_shift_id']
        shift = self.env['utility.cashier.shift'].search([
            ('cashier_id', '=', self.env.user.id),
            ('state', '=', 'open'),
        ], limit=1)
        return shift.id if shift else False

    @api.model
    def _default_collector_shift(self):
        if self.env.context.get('collector_shift_id'):
            return self.env.context['collector_shift_id']
        shift = self.env['utility.collector.shift'].search([
            ('collector_id', '=', self.env.user.id),
            ('state', '=', 'open'),
        ], limit=1)
        return shift.id if shift else False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
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
            if payment.date_range_id.work_type != 'payment' or payment.date_range_id.parent_id != order.date_range_id:
                raise ValidationError(_('فترة التحصيل يجب أن تكون فترة دفع مرتبطة بفترة قراءة الفاتورة.'))
            if order.state == 'cancel':
                raise ValidationError(
                    'لا يمكن تسجيل دفعة على فاتورة ملغاة [%s]. يُرجى التحقق من رقم الفاتورة.' % order.name
                )
            if order.bill_state == 'paid' and order.balance_due <= 0:
                raise ValidationError(
                    'الفاتورة [%s] مدفوعة بالكامل بالفعل. لا حاجة لتسجيل دفعة إضافية.' % order.name
                )
        res = super().action_post()
        utility_payments = self.filtered('utility_sale_order_id')
        for payment in utility_payments:
            payment._reconcile_utility_sale_order()
        utility_payments._create_payment_notification()
        return res

    def _reconcile_utility_sale_order(self):
        self.ensure_one()
        order = self.utility_sale_order_id
        if not order or not self.move_id:
            return
        invoices = (order.invoice_ids | order.utility_move_ids).filtered(lambda m: m.state == 'posted' and m.payment_state != 'paid')
        if not invoices:
            return
        payment_lines = self.move_id.line_ids.filtered(
            lambda line: not line.reconciled and line.account_id.account_type == 'asset_receivable'
        )
        invoice_lines = invoices.mapped('line_ids').filtered(
            lambda line: not line.reconciled and line.account_id.account_type == 'asset_receivable'
        )
        lines = payment_lines | invoice_lines
        if lines:
            lines.reconcile()
