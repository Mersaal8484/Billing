from odoo import api, fields, models, _


class PropertyDeposit(models.Model):
    _name = 'property.deposit'
    _description = 'Security Deposit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_received desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='lease_id.company_id', store=True)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    currency_id = fields.Many2one('res.currency', related='lease_id.currency_id', store=True, readonly=True)

    name = fields.Char(string='Deposit Reference', required=True, index=True,
                       default=lambda self: _('New'))
    lease_id = fields.Many2one('property.lease', string='Lease', required=True, index=True)
    tenant_id = fields.Many2one('property.tenant', string='Tenant', required=True, index=True)
    unit_id = fields.Many2one('property.unit', string='Unit', index=True)
    property_id = fields.Many2one('property.property', string='Property', related='unit_id.property_id', store=True)

    amount = fields.Monetary(string='Deposit Amount', required=True)
    date_received = fields.Date(string='Date Received', required=True,
                                default=fields.Date.today, tracking=True)

    state = fields.Selection([
        ('held', 'Held'),
        ('partial_refund', 'Partially Refunded'),
        ('refunded', 'Fully Refunded'),
        ('forfeited', 'Forfeited'),
    ], string='Status', default='held', tracking=True)

    refund_amount = fields.Monetary(string='Refund Amount', default=0.0)
    refund_date = fields.Date(string='Refund Date')
    deductions = fields.Monetary(string='Deductions', compute='_compute_deductions', store=True)
    deduction_reason = fields.Text(string='Deduction Reason')

    receipt_payment_id = fields.Many2one('property.payment', string='Receipt Payment')
    payment_id = fields.Many2one('property.payment', string='Refund Payment')
    override_exchange_rate = fields.Boolean(string='Override Exchange Rate', default=False, tracking=True)
    exchange_rate = fields.Float(string='Exchange Rate', default=1.0, digits=(12, 6), tracking=True)
    notes = fields.Text(string='Notes')

    @api.depends('amount', 'refund_amount')
    def _compute_deductions(self):
        for rec in self:
            rec.deductions = rec.amount - rec.refund_amount

    def _create_receipt_move(self):
        self.ensure_one()
        property_rec = self.lease_id.property_id
        journal = property_rec._get_journal_for_method('deposit') if property_rec else False
        liquidity_account = property_rec._get_cash_account() if property_rec else False
        liability_account = property_rec._get_deposit_liability_account() if property_rec else False
        if not journal or not liquidity_account or not liability_account:
            return False
        if self.override_exchange_rate:
            company_amount = self.amount * (self.exchange_rate or 1.0)
        elif self.currency_id == self.company_currency_id:
            company_amount = self.amount
        else:
            try:
                company_amount = self.currency_id._convert(
                    self.amount,
                    self.company_currency_id,
                    self.company_id,
                    self.date_received or fields.Date.context_today(self),
                )
            except Exception:
                company_amount = self.amount
        liquidity_line = {
            'name': self.name,
            'partner_id': self.tenant_id.partner_id.id,
            'account_id': liquidity_account.id,
            'debit': company_amount,
            'credit': 0.0,
            'currency_id': self.currency_id.id if self.currency_id != self.company_currency_id else False,
            'amount_currency': self.amount if self.currency_id != self.company_currency_id else 0.0,
        }
        liability_line = {
            'name': self.name,
            'partner_id': self.tenant_id.partner_id.id,
            'account_id': liability_account.id,
            'debit': 0.0,
            'credit': company_amount,
            'currency_id': self.currency_id.id if self.currency_id != self.company_currency_id else False,
            'amount_currency': -self.amount if self.currency_id != self.company_currency_id else 0.0,
        }
        if self.unit_id and self.unit_id.analytic_account_id:
            liability_line['analytic_distribution'] = {str(self.unit_id.analytic_account_id.id): 100.0}

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': self.date_received,
            'ref': self.name,
            'journal_id': journal.id,
            'currency_id': self.currency_id.id,
            'line_ids': [
                (0, 0, liquidity_line),
                (0, 0, liability_line),
            ],
        })
        move.action_post()
        return move

    def action_refund(self, amount=None):
        self.ensure_one()
        refund_amt = amount or self.amount
        payment = self.env['property.payment'].create({
            'lease_id': self.lease_id.id,
            'tenant_id': self.tenant_id.id,
            'unit_id': self.unit_id.id,
            'property_id': self.property_id.id,
            'amount': refund_amt,
            'currency_id': self.currency_id.id,
            'payment_type': 'refund',
            'payment_method': 'cash',
            'date': fields.Date.today(),
            'state': 'confirmed',
            'journal_id': self.lease_id.property_id._get_journal_for_method('deposit').id if self.lease_id and self.lease_id.property_id else False,
        })
        payment.action_paid()
        self.write({
            'refund_amount': refund_amt,
            'refund_date': fields.Date.today(),
            'state': 'refunded' if refund_amt >= self.amount else 'partial_refund',
            'payment_id': payment.id,
        })

    def action_forfeit(self):
        self.write({'state': 'forfeited'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                seq = self.env['ir.sequence'].next_by_code('property.deposit')
                vals['name'] = seq or '/'
        return super().create(vals_list)
