from odoo import api, fields, models, _


class UtilityAdjustment(models.Model):
    _name = 'utility.adjustment'
    _description = 'تسوية'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    reference = fields.Char('المرجع', required=True, default=lambda self: _('جديد'))
    date = fields.Datetime('التاريخ', default=fields.Datetime.now)
    customer_id = fields.Many2one('res.partner', string='العميل', required=True)
    account_id = fields.Many2one('utility.customer', string='الحساب', required=True)
    adjustment_type = fields.Selection([
        ('credit', 'رصيد'),
        ('debit', 'خصم'),
        ('emergency_credit', 'رصيد طوارئ'),
        ('compensation', 'تعويض'),
        ('correction', 'تصحيح'),
    ], string='نوع التسوية', required=True)
    amount = fields.Monetary(string='المبلغ', required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    balance_before = fields.Monetary(compute='_compute_balances', string='الرصيد قبل', store=True)
    balance_after = fields.Monetary(compute='_compute_balances', string='الرصيد بعد', store=True)
    reason = fields.Text(string='السبب', required=True)
    approved_by = fields.Many2one('res.users', string='معتمد من')
    operator_id = fields.Many2one('res.users', string='المشغل', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('approved', 'معتمد'),
        ('applied', 'مُطبّق'),
        ('cancelled', 'ملغى'),
    ], default='draft', string='الحالة', tracking=True)

    @api.depends('account_id', 'amount', 'adjustment_type')
    def _compute_balances(self):
        for rec in self:
            current_balance = rec.account_id.prepaid_balance if rec.account_id else 0.0
            rec.balance_before = current_balance
            if rec.adjustment_type in ('credit', 'emergency_credit', 'compensation'):
                rec.balance_after = current_balance + (rec.amount or 0.0)
            elif rec.adjustment_type in ('debit', 'correction'):
                rec.balance_after = current_balance - (rec.amount or 0.0)
            else:
                rec.balance_after = current_balance

    def action_approve(self):
        self.ensure_one()
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
        })

    def action_apply(self):
        self.ensure_one()
        if self.state != 'approved':
            raise models.ValidationError(_('يجب اعتماد التسوية قبل تطبيقها.'))
        if self.adjustment_type in ('credit', 'emergency_credit', 'compensation'):
            self.account_id._create_balance_transaction(
                'adjustment', self.amount, source_ref=self,
                notes=_('تسوية %s: %s') % (self.reference, self.reason))
        elif self.adjustment_type in ('debit', 'correction'):
            self.account_id._create_balance_transaction(
                'adjustment', -self.amount, source_ref=self,
                notes=_('تسوية %s: %s') % (self.reference, self.reason))
        self.state = 'applied'

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancelled'

    @api.model
    def create(self, vals):
        if vals.get('reference', _('جديد')) == _('جديد'):
            vals['reference'] = self.env['ir.sequence'].next_by_code('utility.adjustment') or _('جديد')
        return super(UtilityAdjustment, self).create(vals)
