import secrets

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityPaymentGatewayTransaction(models.Model):
    _name = 'utility.payment.gateway.transaction'
    _description = 'معاملة بوابة دفع كهرباء'
    _order = 'create_date desc, id desc'

    name = fields.Char('المرجع', required=True, default=lambda self: _('New'), copy=False, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='الشركة', related='sale_order_id.company_id',
        store=True, readonly=True, index=True,
    )
    provider_id = fields.Many2one(
        'utility.integration.provider', string='مزود الدفع', required=True,
        domain=[('is_payment_capable', '=', True), ('active', '=', True)])
    payment_direction = fields.Selection([
        ('inbound', 'وارد (تحصيل من المشترك)'),
        ('outbound', 'صادر (إرجاع/استرداد للمشترك)'),
    ], string='اتجاه الدفع', default='inbound', required=True, index=True)
    sale_order_id = fields.Many2one('sale.order', string='الفاتورة', required=True, ondelete='restrict')
    customer_id = fields.Many2one('utility.customer', string='الحساب', related='sale_order_id.customer_id', store=True)
    partner_id = fields.Many2one('res.partner', string='المشترك', related='sale_order_id.partner_id', store=True)
    currency_id = fields.Many2one('res.currency', string='العملة', related='sale_order_id.currency_id', store=True)
    amount = fields.Monetary('المبلغ', required=True, currency_field='currency_id')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('pending', 'بانتظار التأكيد'),
        ('done', 'مؤكد'),
        ('failed', 'فشل'),
        ('cancelled', 'ملغى'),
    ], default='draft', string='الحالة', index=True)
    access_token = fields.Char('رمز الوصول', readonly=True, copy=False)
    provider_reference = fields.Char('مرجع المزود')
    payment_id = fields.Many2one('account.payment', string='سند الدفع', readonly=True)
    request_payload = fields.Text('طلب المزود')
    callback_payload = fields.Text('رد المزود')
    error_message = fields.Text('رسالة الخطأ')

    @api.onchange('provider_id')
    def _onchange_provider_id(self):
        if self.provider_id and self.provider_id.payment_direction in ('inbound', 'outbound'):
            self.payment_direction = self.provider_id.payment_direction

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.payment.gateway.transaction') or _('New')
            vals.setdefault('access_token', secrets.token_urlsafe(24))
        return super().create(vals_list)

    def action_mark_pending(self):
        for tx in self:
            if tx.state != 'draft':
                raise ValidationError(_('يمكن إرسال المعاملات المسودة فقط إلى مزود الدفع.'))
            if tx.amount <= 0:
                raise ValidationError(_('مبلغ معاملة الدفع يجب أن يكون أكبر من صفر.'))
            if tx.payment_direction == 'inbound':
                if tx.sale_order_id.bill_state in ('paid', 'cancelled'):
                    raise ValidationError(_('الفاتورة غير قابلة للدفع.'))
                if tx.amount > tx.sale_order_id.balance_due:
                    raise ValidationError(_('مبلغ الدفع لا يمكن أن يتجاوز الرصيد المستحق.'))
            if tx.provider_id.company_id and tx.provider_id.company_id != tx.company_id:
                raise ValidationError(_('مزود الدفع والفاتورة يجب أن يتبعا نفس الشركة.'))
            if not tx.provider_id.supports_direction(tx.payment_direction):
                raise ValidationError(_('مزود الدفع المختار (%s) لا يدعم اتجاه الدفع (%s).') % (
                    tx.provider_id.name, tx.payment_direction
                ))
            payload = {
                'reference': tx.name,
                'amount': tx.amount,
                'currency': tx.currency_id.name,
                'payment_direction': tx.payment_direction,
                'bill': tx.sale_order_id.name,
                'customer': tx.customer_id.customer_number if tx.customer_id else False,
                'callback_token': tx.access_token,
            }
            log = tx.provider_id.call_json(payload, 'payment.create', record=tx)
            tx.write({
                'state': 'pending' if log.state == 'success' else 'failed',
                'request_payload': log.request_payload,
                'error_message': log.error_message,
            })

    def action_confirm_payment(self, provider_reference=False, callback_payload=False):
        """Confirm a pending gateway transaction exactly once and post its payment (inbound or outbound)."""
        for tx in self:
            self.env.flush_all()
            self.env.cr.execute(
                "SELECT id FROM utility_payment_gateway_transaction WHERE id = %s FOR UPDATE",
                [tx.id],
            )
            tx.invalidate_cache(['state', 'payment_id', 'provider_reference'])
            if tx.state == 'done':
                continue
            if tx.state != 'pending':
                raise ValidationError(_('يمكن تأكيد معاملات الدفع المعلقة فقط.'))

            order = tx.sale_order_id
            self.env.cr.execute(
                "SELECT id FROM sale_order WHERE id = %s FOR UPDATE",
                [order.id],
            )
            order.invalidate_cache(['bill_state', 'balance_due'])

            if tx.payment_direction == 'inbound':
                if order.bill_state in ('paid', 'cancelled'):
                    raise ValidationError(_('الفاتورة غير قابلة للدفع.'))
                if tx.amount <= 0 or tx.amount > order.balance_due:
                    raise ValidationError(_('مبلغ الدفع غير صالح أو يتجاوز الرصيد المستحق.'))
            else:
                if tx.amount <= 0:
                    raise ValidationError(_('مبلغ الصرف يجب أن يكون أكبر من صفر.'))

            if tx.provider_id.company_id and tx.provider_id.company_id != tx.company_id:
                raise ValidationError(_('مزود الدفع والفاتورة يجب أن يتبعا نفس الشركة.'))

            if provider_reference:
                duplicate = self.search([
                    ('id', '!=', tx.id),
                    ('provider_id', '=', tx.provider_id.id),
                    ('provider_reference', '=', provider_reference),
                    ('state', '=', 'done'),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_('مرجع مزود الدفع مستخدم مسبقاً.'))

            company = tx.company_id
            tx_company = tx.with_company(company)

            direction = tx.payment_direction or 'inbound'
            journal = tx.provider_id._get_payment_journal(direction=direction, company=company)
            if not journal:
                raise ValidationError(_('لم يتم العثور على يومية دفع مناسبة للمعاملة.'))

            if direction == 'inbound':
                method_line = journal.inbound_payment_method_line_ids[:1]
            else:
                method_line = journal.outbound_payment_method_line_ids[:1]

            if not method_line:
                raise ValidationError(_('لم يتم العثور على طريقة دفع معتمدة في اليومية المختارة (%s).') % journal.display_name)

            payment = tx_company.env['account.payment'].sudo().create({
                'partner_id': order.partner_id.id,
                'amount': tx.amount,
                'payment_type': direction,  # 'inbound' or 'outbound'
                'partner_type': 'customer',
                'journal_id': journal.id,
                'payment_method_line_id': method_line.id,
                'utility_sale_order_id': order.id,
                'utility_invoice_id': (
                    order._get_posted_utility_moves().id
                    if len(order._get_posted_utility_moves()) == 1 else False
                ),
                'utility_payment_method': 'electronic',
                'electronic_doc_no': provider_reference or tx.provider_reference or tx.name,
                'date': fields.Date.context_today(tx_company),
            })
            payment.action_post()
            tx.write({
                'state': 'done',
                'payment_id': payment.id,
                'provider_reference': provider_reference or tx.provider_reference,
                'callback_payload': callback_payload or tx.callback_payload,
                'error_message': False,
            })
