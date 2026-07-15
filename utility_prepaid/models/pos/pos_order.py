import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'
    _description = 'أمر نقاط بيع - شحن كهرباء'

    is_prepaid_vending = fields.Boolean('بيع كهرباء مسبق الدفع', default=False)
    utility_account_id = fields.Many2one('utility.customer', 'حساب الكهرباء', index=True)
    utility_meter_id = fields.Many2one('utility.meter', 'العداد', index=True)
    vending_request_id = fields.Many2one('utility.vending.request', 'طلب البيع',
        copy=False, index=True)
    vending_amount = fields.Monetary('مبلغ الشحن', currency_field='currency_id')
    vending_kwh = fields.Float('kWh المشتراة', digits=(12, 3))
    vending_status = fields.Selection(related='vending_request_id.state',
        string='حالة البيع', store=True)

    cashier_shift_id = fields.Many2one('utility.cashier.shift', 'الوردية', index=True)
    token_id = fields.Many2one('utility.token', 'التوكن', readonly=True, index=True)
    token_status = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('generated', 'تم التوليد'),
        ('failed', 'فشل'),
        ('cancelled', 'ملغي'),
    ], 'حالة التوكن', default='pending')
    sms_sent = fields.Boolean('تم إرسال SMS')
    reversal_id = fields.Many2one('utility.vending.reversal', 'طلب العكس', index=True)

    energy_charge = fields.Monetary('قيمة الطاقة', currency_field='currency_id')
    service_charge = fields.Monetary('رسوم الخدمة', currency_field='currency_id')
    tax_amount = fields.Monetary('الضريبة', currency_field='currency_id')
    debt_recovery_charge = fields.Monetary('استقطاع الديون', currency_field='currency_id')

    @api.model
    def _order_fields(self, ui_order):
        order_fields = super()._order_fields(ui_order)
        if 'utility_account_id' in ui_order:
            order_fields['utility_account_id'] = ui_order.get('utility_account_id')
        if 'utility_meter_id' in ui_order:
            order_fields['utility_meter_id'] = ui_order.get('utility_meter_id')
        if 'utility_kwh' in ui_order:
            order_fields['vending_kwh'] = ui_order.get('utility_kwh')
        if 'utility_amount' in ui_order:
            order_fields['vending_amount'] = ui_order.get('utility_amount')
        if 'is_prepaid_vending' in ui_order:
            order_fields['is_prepaid_vending'] = ui_order.get('is_prepaid_vending')
        return order_fields

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('cashier_shift_id'):
                shift = self.env['utility.cashier.shift'].search([
                    ('cashier_id', '=', self.env.user.id),
                    ('state', '=', 'open'),
                ], limit=1)
                if shift:
                    vals['cashier_shift_id'] = shift.id
        return super().create(vals_list)

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        for order in self:
            if not order.is_prepaid_vending:
                continue
            if not order.utility_account_id or not order.utility_meter_id:
                continue
            if order.token_status == 'generated':
                continue
            try:
                order._create_vending_request()
                order._generate_token()
                order._record_vending_transaction()
            except Exception:
                _logger.exception('POS vending failed for order %s', order.name)
        return res

    def _create_vending_request(self):
        self.ensure_one()
        if self.vending_request_id:
            return self.vending_request_id

        channel = self.env['utility.vending.channel'].search([
            ('channel_type', '=', 'pos'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

        vals = {
            'company_id': self.company_id.id,
            'pos_order_id': self.id,
            'account_id': self.utility_account_id.id,
            'meter_id': self.utility_meter_id.id,
            'gross_amount': self.vending_amount or self.amount_total,
            'channel_id': channel.id if channel else False,
            'operator_id': self.user_id.id,
        }
        request = self.env['utility.vending.request'].create(vals)
        request.action_quote()
        request.action_confirm()
        self.vending_request_id = request.id
        return request

    def _generate_token(self):
        self.ensure_one()
        if not self.vending_request_id:
            return
        self.vending_request_id.action_mark_paid()
        self.vending_request_id.action_submit_to_sts()

        if self.vending_request_id.state == 'token_generated':
            token = self.env['utility.token'].search([
                ('vending_request_id', '=', self.vending_request_id.id),
                ('status', '=', 'success'),
            ], limit=1)
            if token:
                self.token_id = token.id
                self.token_status = 'generated'
                self._send_token_notification()
        elif self.vending_request_id.state == 'token_failed':
            self.token_status = 'failed'

    def _record_vending_transaction(self):
        self.ensure_one()
        if not self.utility_account_id:
            return
        self.env['utility.transaction'].create({
            'company_id': self.company_id.id,
            'reference': self.env['ir.sequence'].next_by_code('utility.transaction') or '/',
            'transaction_type': 'vending',
            'amount': self.vending_amount or self.amount_total,
            'partner_id': self.partner_id.id,
            'account_id': self.utility_account_id.id,
            'meter_id': self.utility_meter_id.id,
            'pos_order_id': self.id,
            'vending_request_id': self.vending_request_id.id if self.vending_request_id else False,
            'operator_id': self.user_id.id,
            'notes': _('بيع مسبق الدفع عبر POS: %s') % self.name,
        })

        if self.vending_kwh:
            self.utility_account_id.total_kwh_purchased = (
                (self.utility_account_id.total_kwh_purchased or 0.0) + self.vending_kwh)
        self.utility_account_id.total_purchases = (
            (self.utility_account_id.total_purchases or 0.0) + (self.vending_amount or 0.0))
        self.utility_account_id.last_purchase_date = fields.Date.context_today(self.utility_account_id)

    def _send_token_notification(self):
        self.ensure_one()
        if self.token_id and self.token_id.status == 'success':
            if self.company_id.enable_token_sms and self.partner_id.mobile:
                try:
                    self.token_id._send_token_sms()
                    self.sms_sent = True
                except Exception:
                    _logger.exception('Failed to send SMS for POS order %s', self.name)

    def action_retry_token(self):
        self.ensure_one()
        if self.vending_request_id:
            self.vending_request_id.action_retry_token()
            if self.vending_request_id.state == 'token_generated':
                token = self.env['utility.token'].search([
                    ('vending_request_id', '=', self.vending_request_id.id),
                    ('status', '=', 'success'),
                ], limit=1)
                if token:
                    self.token_id = token.id
                    self.token_status = 'generated'

    def action_view_vending_request(self):
        self.ensure_one()
        if self.vending_request_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('طلب البيع'),
                'res_model': 'utility.vending.request',
                'res_id': self.vending_request_id.id,
                'view_mode': 'form',
            }


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    is_prepaid_line = fields.Boolean('بند شحن مسبق', default=False)
