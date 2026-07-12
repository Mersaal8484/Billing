from odoo import api, fields, models, _


class PosOrder(models.Model):
    _inherit = 'pos.order'
    _description = 'بيع كود شحن (أمر نقاط بيع)'

    account_id = fields.Many2one('utility.customer', string='حساب الكهرباء', index=True)
    meter_id = fields.Many2one('utility.meter', string='العداد')
    contract_template_id = fields.Many2one('utility.contract.template', string='قالب العقد')

    amount_paid = fields.Monetary(string='المدفوع')
    kwh_purchased = fields.Float(string='kWh المشتراة')
    unit_price = fields.Monetary(string='سعر الوحدة')
    energy_charge = fields.Monetary(string='قيمة الطاقة')
    service_charge = fields.Monetary(string='رسم الخدمة')
    tax_amount = fields.Monetary(string='الضريبة')

    balance_before = fields.Monetary(string='الرصيد قبل')
    balance_after = fields.Monetary(string='الرصيد بعد')

    cashier_shift_id = fields.Many2one('utility.cashier.shift', string='الوردية', index=True)
    token_id = fields.Many2one('utility.token', string='الشفرة', readonly=True)
    token_status = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('generated', 'تم التوليد'),
        ('failed', 'فشل'),
        ('cancelled', 'ملغي'),
    ], string='حالة الشفرة', default='pending')
    sms_sent = fields.Boolean(string='تم إرسال SMS')
    reversal_id = fields.Many2one('utility.reversal', string='الإلغاء')

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

    def _generate_token(self):
        self.ensure_one()
        if not self.account_id or not self.meter_id:
            return
        if self.token_id and self.token_id.status == 'success':
            self.token_status = 'generated'
            return self.token_id
        existing_success = self.env['utility.token'].search([
            ('pos_order_id', '=', self.id),
            ('status', '=', 'success'),
        ], limit=1)
        if existing_success:
            self.write({
                'token_id': existing_success.id,
                'token_status': 'generated',
            })
            return existing_success
        token = self.token_id or self.env['utility.token'].create({
            'pos_order_id': self.id,
            'account_id': self.account_id.id,
            'meter_id': self.meter_id.id,
            'customer_id': self.partner_id.id,
            'contract_template_id': self.contract_template_id.id,
            'amount': self.amount_paid,
            'kwh': self.kwh_purchased,
        })
        token.action_request_token()
        self.token_id = token.id
        if token.status == 'success':
            self.token_status = 'generated'
        else:
            self.token_status = 'failed'
        return token

    def _apply_balance(self):
        self.ensure_one()
        if not self.account_id:
            return
        amount = self.amount_paid or 0.0
        self.balance_before = self.account_id.prepaid_balance or 0.0
        self.account_id._create_balance_transaction(
            'recharge', amount, source_ref=self,
            notes=_('بيع مسبق الدفع: %s') % self.name,
        )
        if self.kwh_purchased:
            self.account_id.total_kwh_purchased = (self.account_id.total_kwh_purchased or 0.0) + self.kwh_purchased
        self.balance_after = self.account_id.prepaid_balance

    def _get_token_html_link(self):
        if self.token_id:
            url = '/web#id=%d&model=utility.token&view_type=form' % self.token_id.id
            return '<a href="%s">%s</a>' % (url, self.token_id.token_number or '')
        return ''

    def action_pos_order_paid(self):
        """
        FIX-9: Odoo يستدعي هذه الدالة تلقائياً عند إغلاق طلب POS بعد الدفع.
        نستخدمها لتوليد التوكن وتطبيق الرصيد تلقائياً بدون تدخل يدوي.
        العملية آمنة (idempotent): إذا كان التوكن مولّداً مسبقاً لا يعيد التوليد.
        """
        res = super().action_pos_order_paid()
        for order in self:
            if not order.account_id or not order.meter_id:
                continue
            # idempotency: لا تُطبّق مرة ثانية إذا تمّت العملية
            if order.token_status == 'generated':
                continue
            try:
                order._generate_token()
                order._apply_balance()
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    'POS auto-token/balance failed for order %s', order.name
                )
        return res


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'
    _description = 'بند بيع مسبق الدفع'
