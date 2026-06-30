from odoo import api, fields, models


class UtilityTransaction(models.Model):
    _name = 'utility.transaction'
    _description = 'Utility Transaction'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _log_access = False
    _order = 'date desc, id desc'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    reference = fields.Char(string='Reference', required=True, index=True)
    date = fields.Datetime(default=fields.Datetime.now, string='Date')
    transaction_type = fields.Selection([
        ('sale', 'Sale'),
        ('reversal', 'Reversal'),
        ('adjustment', 'Adjustment'),
        ('emergency_credit', 'Emergency Credit'),
        ('refund', 'Refund'),
    ], string='Transaction Type', required=True)
    amount = fields.Monetary(string='Amount')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    balance_before = fields.Monetary(string='Balance Before')
    balance_after = fields.Monetary(string='Balance After')
    customer_id = fields.Many2one('res.partner', string='Customer')
    account_id = fields.Many2one('utility.customer', string='Account', index=True)
    meter_id = fields.Many2one('utility.meter', string='Meter')
    pos_order_id = fields.Many2one('pos.order', string='POS Order')
    reversal_id = fields.Many2one('utility.reversal', string='Reversal')
    adjustment_id = fields.Many2one('utility.adjustment', string='Adjustment')
    operator_id = fields.Many2one('res.users', string='Operator')
    notes = fields.Text(string='Notes')

    @api.model
    def create_transaction(self, ttype, account, amount, pos_order=None,
                           reversal=None, adjustment=None, notes=''):
        balance_before = account.balance
        sign = 1.0
        if ttype in ('reversal', 'refund'):
            sign = -1.0
        balance_after = balance_before + (amount * sign)
        vals = {
            'reference': self.env['ir.sequence'].next_by_code('utility.transaction') or '/',
            'transaction_type': ttype,
            'amount': amount,
            'balance_before': balance_before,
            'balance_after': balance_after,
            'customer_id': account.customer_id.id,
            'account_id': account.id,
            'meter_id': account.meter_id.id if account.meter_id else False,
            'pos_order_id': pos_order.id if pos_order else False,
            'reversal_id': reversal.id if reversal else False,
            'adjustment_id': adjustment.id if adjustment else False,
            'operator_id': self.env.user.id,
            'notes': notes,
        }
        return self.create(vals)
