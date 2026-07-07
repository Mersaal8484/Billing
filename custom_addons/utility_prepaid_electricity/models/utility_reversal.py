from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UtilityReversal(models.Model):
    _name = 'utility.reversal'
    _description = 'Transaction Reversal'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'reference'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    reference = fields.Char(string='Reference', required=True, index=True, copy=False,
                            default=lambda self: _('New'))
    date = fields.Datetime(string='Reversal Date', default=fields.Datetime.now, required=True, index=True)

    customer_id = fields.Many2one('utility.customer', string='Customer', required=True, index=True, tracking=True)
    account_id = fields.Many2one('utility.account', string='Account', required=True, index=True, tracking=True)
    meter_id = fields.Many2one('utility.meter', string='Meter', index=True)

    sale_id = fields.Many2one('utility.sale', string='Original Sale', index=True)
    payment_id = fields.Many2one('utility.payment', string='Original Payment', index=True)

    reversal_type = fields.Selection([
        ('full', 'Full Reversal'),
        ('partial', 'Partial Reversal'),
    ], string='Reversal Type', required=True, default='full')
    amount = fields.Monetary(string='Amount', required=True, digits=(16, 4))

    reason = fields.Text(string='Reason', required=True, tracking=True)
    approved_by = fields.Many2one('res.users', string='Approved By', tracking=True)
    operator_id = fields.Many2one('res.users', string='Operator', default=lambda self: self.env.user, index=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', index=True, tracking=True, required=True)

    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('check_amount_positive', 'CHECK(amount > 0)', 'Reversal amount must be positive!'),
    ]

    def action_approve(self):
        self.write({'state': 'approved', 'approved_by': self.env.user.id})

    def action_complete(self):
        self.ensure_one()
        if self.state not in ('approved', 'draft'):
            raise UserError(_('Reversal must be approved first.'))

        # Revert the account balance
        self.account_id.balance = max(0.0, self.account_id.balance - self.amount)

        # Mark related sale as reversed
        if self.sale_id:
            self.sale_id.write({
                'state': 'reversed',
                'reversal_id': self.id,
            })
            # Mark token as cancelled
            if self.sale_id.token_id:
                self.sale_id.token_id.action_cancel()

        # Mark related payment as reversed
        if self.payment_id:
            self.payment_id.write({
                'state': 'reversed',
                'reversal_id': self.id,
            })

        # Create audit trail
        self.env['utility.audit'].create({
            'model': 'utility.reversal',
            'res_id': self.id,
            'action': 'complete',
            'description': f'Reversal {self.reference} completed. Amount: {self.amount}',
            'user_id': self.env.user.id,
        })

        # Create transaction log
        self.env['utility.transaction'].create_transaction(
            'reversal', self.account_id, self.amount,
            reversal=self, notes=self.reason
        )

        self.write({'state': 'completed'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    @api.model
    def create(self, vals):
        if vals.get('reference', _('New')) == _('New'):
            vals['reference'] = self.env['ir.sequence'].next_by_code('utility.reversal') or _('New')
        return super().create(vals)
