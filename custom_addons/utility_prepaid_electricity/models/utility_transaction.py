from odoo import api, fields, models, _


class UtilityTransaction(models.Model):
    _name = 'utility.transaction'
    _description = 'Financial Transaction Log'
    _order = 'date desc, id desc'
    _log_access = False
    _rec_name = 'reference'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    reference = fields.Char(string='Reference', required=True, index=True)
    date = fields.Datetime(string='Transaction Date', default=fields.Datetime.now, required=True, index=True)

    customer_id = fields.Many2one('utility.customer', string='Customer', index=True)
    account_id = fields.Many2one('utility.account', string='Account', index=True)
    meter_id = fields.Many2one('utility.meter', string='Meter', index=True)

    transaction_type = fields.Selection([
        ('sale', 'Prepaid Sale'),
        ('payment', 'Payment'),
        ('reversal', 'Reversal'),
        ('adjustment', 'Adjustment'),
        ('emergency_credit', 'Emergency Credit'),
        ('refund', 'Refund'),
    ], string='Transaction Type', required=True, index=True)

    amount = fields.Monetary(string='Amount', required=True, digits=(16, 4))
    balance_before = fields.Monetary(string='Balance Before', digits=(16, 4))
    balance_after = fields.Monetary(string='Balance After', digits=(16, 4))

    sale_id = fields.Many2one('utility.sale', string='Related Sale', index=True)
    payment_id = fields.Many2one('utility.payment', string='Related Payment', index=True)
    reversal_id = fields.Many2one('utility.reversal', string='Related Reversal', index=True)
    adjustment_id = fields.Many2one('utility.adjustment', string='Related Adjustment', index=True)

    operator_id = fields.Many2one('res.users', string='Operator', index=True)
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('reference_uniq', 'UNIQUE(reference)', 'Transaction reference must be unique!'),
    ]

    @api.model
    def create_transaction(self, ttype, account, amount, sale=None, payment=None,
                           reversal=None, adjustment=None, notes=''):
        """Create a transaction log entry with balance tracking."""
        account_balance = account.balance if account else 0.0
        if ttype in ('sale', 'payment', 'adjustment', 'emergency_credit'):
            new_balance = account_balance + amount
        elif ttype in ('reversal', 'refund'):
            new_balance = account_balance - amount
        else:
            new_balance = account_balance
        reference = self.env['ir.sequence'].next_by_code('utility.transaction') or _('New')
        return self.create({
            'reference': reference,
            'transaction_type': ttype,
            'customer_id': account.customer_id.id if account else False,
            'account_id': account.id if account else False,
            'meter_id': account.meter_id.id if account and account.meter_id else False,
            'amount': amount,
            'balance_before': account_balance,
            'balance_after': new_balance,
            'sale_id': sale.id if sale else False,
            'payment_id': payment.id if payment else False,
            'reversal_id': reversal.id if reversal else False,
            'adjustment_id': adjustment.id if adjustment else False,
            'operator_id': self.env.user.id,
            'notes': notes,
        })
