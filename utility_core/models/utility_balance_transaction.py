from odoo import api, fields, models, _


class UtilityCustomerBalanceTransaction(models.Model):
    _name = 'utility.customer.balance.transaction'
    _description = 'حركة رصيد مشترك (دفتر يومية المحفظة)'
    _rec_name = 'reference'
    _order = 'date desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    customer_id = fields.Many2one(
        'utility.customer', string='الحساب',
        required=True, index=True, ondelete='cascade')

    date = fields.Datetime(default=fields.Datetime.now, string='التاريخ', required=True)
    reference = fields.Char(string='المرجع', required=True, index=True,
                            default=lambda self: _('جديد'))

    transaction_type = fields.Selection([
        ('recharge', 'شحن رصيد'),
        ('consumption', 'استهلاك'),
        ('adjustment', 'تسوية يدوية'),
        ('emergency_credit', 'رصيد طوارئ'),
        ('reversal', 'إلغاء/استرداد'),
    ], string='نوع الحركة', required=True)

    amount = fields.Monetary(string='المبلغ', required=True)
    balance_before = fields.Monetary(string='الرصيد قبل', default=0.0)
    balance_after = fields.Monetary(string='الرصيد بعد', default=0.0)

    source_model = fields.Char(string='النموذج المصدر')
    source_id = fields.Integer(string='معرف السجل المصدر')

    notes = fields.Text(string='ملاحظات')
    operator_id = fields.Many2one('res.users', string='المشغل',
                                   default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('posted', 'مرحّل'),
        ('cancelled', 'ملغى'),
    ], string='الحالة', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('جديد')) == _('جديد'):
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'utility.customer.balance.transaction') or _('جديد')
        return super().create(vals_list)

    def action_post(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            rec._update_customer_balance()
            rec.state = 'posted'

    def _update_customer_balance(self):
        self.ensure_one()
        customer = self.customer_id
        if not customer:
            return
        balance_before = customer.prepaid_balance
        balance_after = balance_before + self.amount
        self.write({
            'balance_before': balance_before,
            'balance_after': balance_after,
        })

    def action_cancel(self):
        self.state = 'cancelled'
