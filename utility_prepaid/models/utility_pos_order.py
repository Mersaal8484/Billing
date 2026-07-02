from odoo import api, fields, models, _


class PosOrder(models.Model):
    _inherit = 'pos.order'
    _description = 'Prepaid Token Sale (POS Order)'

    account_id = fields.Many2one('utility.customer', string='حساب الكهرباء', index=True)
    meter_id = fields.Many2one('utility.meter', string='العداد')
    contract_template_id = fields.Many2one('utility.contract.template', string='قالب العقد')

    amount_paid = fields.Monetary(string='المدفوع')
    kwh_purchased = fields.Float(string='kWh المشتراة')
    unit_price = fields.Float(string='سعر الوحدة')
    energy_charge = fields.Monetary(string='قيمة الطاقة')
    service_charge = fields.Monetary(string='رسم الخدمة')
    tax_amount = fields.Monetary(string='الضريبة')

    balance_before = fields.Monetary(string='الرصيد قبل')
    balance_after = fields.Monetary(string='الرصيد بعد')

    token_id = fields.Many2one('utility.token', string='الشفرة', readonly=True)
    token_status = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('generated', 'تم التوليد'),
        ('failed', 'فشل'),
        ('cancelled', 'ملغي'),
    ], string='حالة الشفرة', default='pending')
    sms_sent = fields.Boolean(string='تم إرسال SMS')
    reversal_id = fields.Many2one('utility.reversal', string='الإلغاء')

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
        self.balance_before = self.account_id.balance or 0.0
        self.account_id._update_balance(amount)
        if self.kwh_purchased:
            self.account_id.total_kwh_purchased = (self.account_id.total_kwh_purchased or 0.0) + self.kwh_purchased
        self.balance_after = self.account_id.balance
        self.env['utility.transaction'].create_transaction(
            'sale', self.account_id, amount, pos_order=self,
            notes=_('Prepaid POS sale: %s') % self.name,
        )

    def _get_token_html_link(self):
        if self.token_id:
            url = '/web#id=%d&model=utility.token&view_type=form' % self.token_id.id
            return '<a href="%s">%s</a>' % (url, self.token_id.token_number or '')
        return ''


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'
    _description = 'Prepaid Sale Line'
