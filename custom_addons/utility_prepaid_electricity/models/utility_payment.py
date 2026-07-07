from odoo import api, fields, models, _
from odoo.exceptions import UserError


class UtilityPayment(models.Model):
    _name = 'utility.payment'
    _description = 'Payment Record'
    _order = 'payment_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'payment_reference'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    payment_reference = fields.Char(string='Payment Reference', required=True, index=True, copy=False,
                                    default=lambda self: _('New'))
    payment_date = fields.Datetime(string='Payment Date', default=fields.Datetime.now, required=True, index=True)

    sale_id = fields.Many2one('utility.sale', string='Related Sale', index=True)
    customer_id = fields.Many2one('utility.customer', string='Customer', required=True, index=True, tracking=True)
    account_id = fields.Many2one('utility.account', string='Account', required=True, index=True, tracking=True)

    amount = fields.Monetary(string='Amount', required=True, digits=(16, 4))
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('pos', 'POS Terminal'),
        ('bank', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('wallet', 'Digital Wallet'),
        ('online', 'Online Payment'),
    ], string='Payment Method', default='cash', required=True, tracking=True)

    reference_number = fields.Char(string='External Reference')
    bank_name = fields.Char(string='Bank Name')
    check_number = fields.Char(string='Check Number')
    mobile_provider = fields.Char(string='Mobile Money Provider')
    wallet_provider = fields.Char(string='Wallet Provider')
    online_gateway = fields.Char(string='Online Gateway')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('reconciled', 'Reconciled'),
        ('reversed', 'Reversed'),
        ('failed', 'Failed'),
    ], string='Status', default='draft', index=True, tracking=True, required=True)

    operator_id = fields.Many2one('res.users', string='Operator', default=lambda self: self.env.user, index=True)
    notes = fields.Text(string='Notes')

    reversal_id = fields.Many2one('utility.reversal', string='Reversal', readonly=True, copy=False)

    _sql_constraints = [
        ('payment_ref_uniq', 'UNIQUE(payment_reference, company_id)', 'Payment reference must be unique!'),
        ('check_amount_positive', 'CHECK(amount > 0)', 'Payment amount must be positive!'),
    ]

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_reconcile(self):
        self.write({'state': 'reconciled'})

    def action_reverse(self):
        if not self.env.user.has_group('utility_prepaid_electricity.group_utility_supervisor'):
            raise UserError(_('Only supervisors can reverse payments.'))
        return {
            'name': _('Reverse Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'utility.reversal',
            'view_mode': 'form',
            'context': {
                'default_payment_id': self.id,
                'default_account_id': self.account_id.id,
                'default_customer_id': self.customer_id.id,
                'default_amount': self.amount,
                'default_reason': 'Payment reversal',
            },
        }

    def action_fail(self):
        self.write({'state': 'failed'})

    @api.model
    def create(self, vals):
        if vals.get('payment_reference', _('New')) == _('New'):
            vals['payment_reference'] = self.env['ir.sequence'].next_by_code('utility.payment') or _('New')
        return super().create(vals)
