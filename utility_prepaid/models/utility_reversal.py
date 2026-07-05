from odoo import api, fields, models, _


class UtilityReversal(models.Model):
    _name = 'utility.reversal'
    _description = 'إلغاء'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    reference = fields.Char('المرجع', required=True, default=lambda self: _('جديد'))
    date = fields.Datetime('التاريخ', default=fields.Datetime.now)
    reversal_type = fields.Selection([
        ('full', 'كامل'),
        ('partial', 'جزئي'),
    ], string='نوع الإلغاء', required=True, default='full')
    amount = fields.Monetary(string='المبلغ', required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    customer_id = fields.Many2one('res.partner', string='العميل', required=True)
    account_id = fields.Many2one('utility.customer', string='الحساب', required=True)
    meter_id = fields.Many2one('utility.meter', string='العداد')
    pos_order_id = fields.Many2one('pos.order', string='أمر نقاط البيع')
    reason = fields.Text(string='السبب', required=True)
    approved_by = fields.Many2one('res.users', string='معتمد من')
    operator_id = fields.Many2one('res.users', string='المشغل', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('approved', 'معتمد'),
        ('completed', 'مكتمل'),
        ('rejected', 'مرفوض'),
    ], default='draft', string='الحالة', tracking=True)

    def action_approve(self):
        self.ensure_one()
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
        })

    def action_complete(self):
        self.ensure_one()
        if self.state != 'approved':
            raise models.ValidationError(_('يجب اعتماد الإلغاء قبل إكماله.'))
        self.account_id._update_balance(-self.amount)
        if self.pos_order_id:
            self.pos_order_id.write({
                'reversal_id': self.id,
            })
        self.env['utility.transaction'].create_transaction(
            'reversal', self.account_id, self.amount, reversal=self,
            pos_order=self.pos_order_id,
            notes=_('إلغاء %s: %s') % (self.reference, self.reason),
        )
        self.state = 'completed'

    def action_reject(self):
        self.ensure_one()
        self.state = 'rejected'

    @api.model
    def create(self, vals):
        if vals.get('reference', _('جديد')) == _('جديد'):
            vals['reference'] = self.env['ir.sequence'].next_by_code('utility.reversal') or _('جديد')
        return super(UtilityReversal, self).create(vals)
