from odoo import api, fields, models, _


class PosOrder(models.Model):
    _inherit = 'pos.order'
    _description = 'Prepaid Token Sale (POS Order)'

    account_id = fields.Many2one('utility.customer', string='حساب الكهرباء', index=True)
    meter_id = fields.Many2one('utility.meter', string='العداد')
    tariff_id = fields.Many2one('utility.tariff', string='التعرفة')

    amount_paid = fields.Monetary(string='المدفوع')
    kwh_purchased = fields.Float(string='kWh المشتراة')
    unit_price = fields.Float(string='سعر الوحدة')
    energy_charge = fields.Monetary(string='قيمة الطاقة')
    service_charge = fields.Monetary(string='رسم الخدمة')
    fuel_adjustment = fields.Monetary(string='تسعيرة الوقود')
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
        token = self.env['utility.token'].create({
            'pos_order_id': self.id,
            'account_id': self.account_id.id,
            'meter_id': self.meter_id.id,
            'customer_id': self.partner_id.id,
            'tariff_id': self.tariff_id.id,
            'amount': self.amount_paid,
            'kwh': self.kwh_purchased,
        })
        token.action_request_token()
        self.token_id = token.id
        if token.status == 'success':
            self.token_status = 'generated'
        else:
            self.token_status = 'failed'

    def _apply_balance(self):
        self.ensure_one()
        if self.account_id:
            self.account_id._update_balance(self.amount_paid or 0.0)
            self.balance_before = self.account_id.balance - (self.amount_paid or 0.0)
            self.balance_after = self.account_id.balance
        self.env['utility.transaction'].create_transaction(
            'sale', self.account_id, self.amount_paid, pos_order=self,
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
