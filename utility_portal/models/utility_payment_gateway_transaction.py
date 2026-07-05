import secrets

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityPaymentGatewayTransaction(models.Model):
    _name = 'utility.payment.gateway.transaction'
    _description = 'معاملة بوابة دفع كهرباء'
    _order = 'create_date desc, id desc'

    name = fields.Char('المرجع', required=True, default=lambda self: _('New'), copy=False, readonly=True)
    provider_id = fields.Many2one(
        'utility.integration.provider', string='مزود الدفع', required=True,
        domain=[('provider_type', '=', 'payment_gateway'), ('active', '=', True)])
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.payment.gateway.transaction') or _('New')
            vals.setdefault('access_token', secrets.token_urlsafe(24))
        return super().create(vals_list)

    def action_mark_pending(self):
        for tx in self:
            if tx.amount <= 0:
                raise ValidationError(_('مبلغ معاملة الدفع يجب أن يكون أكبر من صفر.'))
            if tx.sale_order_id.bill_state in ('paid', 'cancelled'):
                raise ValidationError(_('الفاتورة غير قابلة للدفع.'))
            payload = {
                'reference': tx.name,
                'amount': tx.amount,
                'currency': tx.currency_id.name,
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
        for tx in self:
            if tx.state == 'done':
                continue
            order = tx.sale_order_id
            if order.bill_state in ('paid', 'cancelled'):
                raise ValidationError(_('الفاتورة غير قابلة للدفع.'))
            journal_id = int(self.env['ir.config_parameter'].sudo().get_param('utility.collection_journal_id', 0) or 0)
            journal = self.env['account.journal'].sudo().browse(journal_id) if journal_id else False
            if not journal or not journal.inbound_payment_method_line_ids:
                journal = self.env['account.journal'].sudo().search([
                    ('type', '=', 'bank'), ('company_id', '=', self.env.company.id),
                ], limit=1)
            if not journal or not journal.inbound_payment_method_line_ids:
                raise ValidationError(_('لم يتم العثور على يومية دفع واردة.'))
            payment = self.env['account.payment'].sudo().create({
                'partner_id': order.partner_id.id,
                'amount': tx.amount,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'journal_id': journal.id,
                'payment_method_line_id': journal.inbound_payment_method_line_ids[:1].id,
                'utility_sale_order_id': order.id,
                'utility_payment_method': 'electronic',
                'electronic_doc_no': provider_reference or tx.provider_reference or tx.name,
                'date': fields.Date.context_today(self),
            })
            payment.action_post()
            tx.write({
                'state': 'done',
                'payment_id': payment.id,
                'provider_reference': provider_reference or tx.provider_reference,
                'callback_payload': callback_payload or tx.callback_payload,
                'error_message': False,
            })
