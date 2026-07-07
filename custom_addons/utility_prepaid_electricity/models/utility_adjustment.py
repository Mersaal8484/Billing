from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityAdjustment(models.Model):
    _name = 'utility.adjustment'
    _description = 'Account Adjustment'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'reference'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    reference = fields.Char(string='Reference', required=True, index=True, copy=False,
                            default=lambda self: _('New'))
    date = fields.Datetime(string='Adjustment Date', default=fields.Datetime.now, required=True, index=True)

    customer_id = fields.Many2one('utility.customer', string='Customer', required=True, index=True, tracking=True)
    account_id = fields.Many2one('utility.account', string='Account', required=True, index=True, tracking=True)

    adjustment_type = fields.Selection([
        ('credit', 'Credit (Add)'),
        ('debit', 'Debit (Deduct)'),
        ('emergency_credit', 'Emergency Credit'),
        ('compensation', 'Compensation'),
        ('correction', 'Correction'),
    ], string='Adjustment Type', required=True, tracking=True)

    amount = fields.Monetary(string='Amount', required=True, digits=(16, 4))
    balance_before = fields.Monetary(string='Balance Before', readonly=True, digits=(16, 4))
    balance_after = fields.Monetary(string='Balance After', compute='_compute_balance_after', store=True, digits=(16, 4))

    reason = fields.Text(string='Reason', required=True, tracking=True)
    approved_by = fields.Many2one('res.users', string='Approved By', tracking=True)
    operator_id = fields.Many2one('res.users', string='Operator', default=lambda self: self.env.user, index=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('applied', 'Applied'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', index=True, tracking=True, required=True)

    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('check_amount_positive', 'CHECK(amount > 0)', 'Adjustment amount must be positive!'),
    ]

    @api.depends('balance_before', 'amount', 'adjustment_type')
    def _compute_balance_after(self):
        for rec in self:
            if rec.adjustment_type in ('credit', 'emergency_credit', 'compensation'):
                rec.balance_after = (rec.balance_before or 0.0) + rec.amount
            else:
                rec.balance_after = (rec.balance_before or 0.0) - rec.amount

    def action_approve(self):
        self.write({'state': 'approved', 'approved_by': self.env.user.id})

    def action_apply(self):
        self.ensure_one()
        if self.state not in ('approved', 'draft'):
            raise ValidationError(_('Adjustment must be approved before applying.'))
        self.balance_before = self.account_id.balance
        if self.adjustment_type in ('credit', 'emergency_credit', 'compensation'):
            self.account_id.balance += self.amount
            if self.adjustment_type == 'emergency_credit':
                self.account_id.emergency_credit_used += self.amount
        else:
            self.account_id.balance = max(0.0, self.account_id.balance - self.amount)
        self.write({'state': 'applied'})
        self.env['utility.transaction'].create_transaction(
            'adjustment', self.account_id, self.amount,
            adjustment=self, notes=self.reason
        )

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    @api.model
    def create(self, vals):
        if vals.get('reference', _('New')) == _('New'):
            vals['reference'] = self.env['ir.sequence'].next_by_code('utility.adjustment') or _('New')
        return super().create(vals)


