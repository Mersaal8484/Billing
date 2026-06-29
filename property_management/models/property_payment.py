from odoo import api, fields, models, _


class PropertyPayment(models.Model):
    _name = 'property.payment'
    _description = 'Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='lease_id.company_id', store=True)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    currency_id = fields.Many2one('res.currency', string='Transaction Currency', required=True, default=lambda self: self.env.company.currency_id)
    journal_id = fields.Many2one('account.journal', string='Journal', domain="[('type','in',('cash','bank','general'))]")
    move_id = fields.Many2one('account.move', string='Journal Entry')
    refund_move_id = fields.Many2one('account.move', string='Refund Journal Entry')

    name = fields.Char(string='Payment Reference', required=True, index=True,
                       default=lambda self: _('New'))
    lease_id = fields.Many2one('property.lease', string='Lease', required=True, index=True)
    schedule_id = fields.Many2one('property.payment.schedule', string='Schedule Item', index=True)
    tenant_id = fields.Many2one('property.tenant', string='Tenant', required=True, index=True)
    unit_id = fields.Many2one('property.unit', string='Unit', index=True)
    property_id = fields.Many2one('property.property', string='Property', index=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account (Unit Cost Center)', related='unit_id.analytic_account_id', store=True, readonly=False)

    date = fields.Date(string='Payment Date', required=True, default=fields.Date.today, tracking=True)
    amount = fields.Monetary(string='Amount', required=True, tracking=True)
    received_amount = fields.Monetary(string='Received Amount', default=0.0)
    change_amount = fields.Monetary(string='Change Amount', compute='_compute_change', store=True)

    payment_type = fields.Selection([
        ('rent', 'Rent Payment'),
        ('advance', 'Advance Payment'),
        ('deposit', 'Security Deposit'),
        ('late_fee', 'Late Fee'),
        ('service_charge', 'Service Charge'),
        ('refund', 'Refund'),
        ('other', 'Other'),
    ], string='Payment Type', default='rent', required=True)

    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('check', 'Check'),
        ('credit_card', 'Credit Card'),
        ('online', 'Online Payment'),
    ], string='Payment Method', default='bank_transfer', required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    reference = fields.Char(string='Reference/Check No.')
    bank_account = fields.Char(string='Bank Account')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    payment_id = fields.Many2one('account.payment', string='Accounting Payment')

    override_exchange_rate = fields.Boolean(string='Override Exchange Rate', default=False, tracking=True)
    exchange_rate = fields.Float(string='Exchange Rate', default=1.0, digits=(12, 6), tracking=True)
    late_fee_applied = fields.Monetary(string='Late Fee Applied', default=0.0)
    company_amount = fields.Monetary(string='Company Currency Amount', compute='_compute_company_amount', store=True, currency_field='company_currency_id')
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('check_amount_positive', 'CHECK(amount > 0)', 'Payment amount must be positive!'),
    ]

    @api.depends('amount', 'received_amount')
    def _compute_change(self):
        for rec in self:
            rec.change_amount = rec.received_amount - rec.amount if rec.received_amount else 0.0

    @api.depends('amount', 'currency_id', 'date', 'override_exchange_rate', 'exchange_rate')
    def _compute_company_amount(self):
        for rec in self:
            if rec.override_exchange_rate:
                rec.company_amount = (rec.amount or 0.0) * (rec.exchange_rate or 1.0)
            else:
                currency = rec.currency_id or rec.company_currency_id
                if currency and rec.company_currency_id:
                    try:
                        rec.company_amount = currency._convert(
                            rec.amount or 0.0,
                            rec.company_currency_id,
                            rec.company_id,
                            rec.date or fields.Date.context_today(self),
                        )
                    except Exception:
                        rec.company_amount = rec.amount or 0.0
                else:
                    rec.company_amount = rec.amount or 0.0

    def _get_liquidity_account(self):
        self.ensure_one()
        if self.journal_id and self.journal_id.default_account_id:
            return self.journal_id.default_account_id
        journal = self._get_journal()
        if journal and journal.default_account_id:
            return journal.default_account_id
        if self.lease_id and self.lease_id.property_id:
            return self.lease_id.property_id._get_cash_account()
        return False

    def _get_counterpart_account(self):
        self.ensure_one()
        property_rec = self.lease_id.property_id if self.lease_id else False
        if self.schedule_id and self.schedule_id.invoice_id:
            receivable_lines = self.schedule_id.invoice_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled)
            if receivable_lines:
                return receivable_lines[0].account_id
            return property_rec._get_receivable_account() if property_rec else False
        if self.payment_type == 'deposit':
            return property_rec._get_deposit_liability_account() if property_rec else False
        if self.payment_type == 'advance':
            return property_rec._get_advance_liability_account() if property_rec else False
        if self.payment_type == 'service_charge':
            return property_rec._get_service_income_account() if property_rec else False
        if self.payment_type == 'refund':
            return property_rec._get_deposit_liability_account() if property_rec else False
        return property_rec._get_rent_income_account() if property_rec else False

    def _get_journal(self):
        self.ensure_one()
        if self.journal_id:
            return self.journal_id
        if self.lease_id and self.lease_id.property_id:
            method = 'deposit' if self.payment_type in ('deposit', 'refund') else ('cash' if self.payment_method == 'cash' else 'bank')
            journal = self.lease_id.property_id._get_journal_for_method(method)
            if journal:
                return journal
        return self.env['account.journal'].search([('company_id', '=', self.company_id.id), ('type', 'in', ('cash', 'bank', 'general'))], limit=1)

    def _create_account_move(self):
        self.ensure_one()
        if self.move_id:
            return self.move_id
        journal = self._get_journal()
        liquidity_account = self._get_liquidity_account()
        counterpart_account = self._get_counterpart_account()
        if not journal or not liquidity_account or not counterpart_account:
            return False
        company_amount = self.company_amount or 0.0
        if not company_amount:
            return False
        is_refund = self.payment_type == 'refund'
        amount_currency = self.amount if self.currency_id and self.currency_id != self.company_currency_id else 0.0
        currency_id = self.currency_id.id if amount_currency else False
        analytic_dist = {str(self.analytic_account_id.id): 100.0} if self.analytic_account_id else False
        debit_line = {
            'name': self.name,
            'partner_id': self.tenant_id.partner_id.id if self.tenant_id and self.tenant_id.partner_id else False,
            'account_id': liquidity_account.id,
            'debit': 0.0 if is_refund else company_amount,
            'credit': company_amount if is_refund else 0.0,
        }
        credit_line = {
            'name': self.name,
            'partner_id': self.tenant_id.partner_id.id if self.tenant_id and self.tenant_id.partner_id else False,
            'account_id': counterpart_account.id,
            'debit': company_amount if is_refund else 0.0,
            'credit': 0.0 if is_refund else company_amount,
        }
        if analytic_dist:
            if is_refund:
                debit_line['analytic_distribution'] = analytic_dist
            else:
                credit_line['analytic_distribution'] = analytic_dist
        if currency_id:
            debit_line.update({'currency_id': currency_id, 'amount_currency': -self.amount if is_refund else self.amount})
            credit_line.update({'currency_id': currency_id, 'amount_currency': self.amount if is_refund else -self.amount})
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': self.date,
            'ref': self.name,
            'journal_id': journal.id,
            'currency_id': currency_id or self.company_currency_id.id,
            'line_ids': [(0, 0, debit_line), (0, 0, credit_line)],
        })
        move.action_post()
        if self.schedule_id and self.schedule_id.invoice_id:
            invoice_receivable = self.schedule_id.invoice_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled)
            payment_receivable = move.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled)
            (invoice_receivable | payment_receivable).reconcile()
        return move

    def _update_schedule_amounts(self):
        pass

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_paid(self):
        for rec in self:
            if rec.state == 'paid' and rec.move_id:
                continue
            move = rec._create_account_move()
            if move:
                rec.move_id = move.id
            rec._update_schedule_amounts()
            rec.state = 'paid'
            if rec.lease_id:
                rec.lease_id._compute_payment_summary()

    def action_refund(self):
        for rec in self:
            if rec.refund_move_id:
                rec.write({'state': 'refunded'})
                continue
            if rec.move_id:
                reversal_lines = []
                for line in rec.move_id.line_ids:
                    reversal_vals = {
                        'name': 'Refund %s' % rec.name,
                        'partner_id': line.partner_id.id,
                        'account_id': line.account_id.id,
                        'debit': line.credit,
                        'credit': line.debit,
                    }
                    if line.analytic_distribution:
                        reversal_vals['analytic_distribution'] = line.analytic_distribution
                    if line.currency_id:
                        reversal_vals['currency_id'] = line.currency_id.id
                        reversal_vals['amount_currency'] = -(line.amount_currency or 0.0)
                    reversal_lines.append((0, 0, reversal_vals))
                refund_move = rec.env['account.move'].create({
                    'move_type': 'entry',
                    'date': fields.Date.context_today(rec),
                    'ref': 'Refund %s' % rec.name,
                    'journal_id': rec.move_id.journal_id.id,
                    'line_ids': reversal_lines,
                })
                refund_move.action_post()
                rec.refund_move_id = refund_move.id
            rec.write({'state': 'refunded'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                seq = self.env['ir.sequence'].next_by_code('property.payment')
                vals['name'] = seq or '/'
            if vals.get('schedule_id'):
                schedule = self.env['property.payment.schedule'].browse(vals['schedule_id'])
                vals['lease_id'] = schedule.lease_id.id
                vals['tenant_id'] = schedule.tenant_id.id or vals.get('tenant_id')
                vals['unit_id'] = schedule.unit_id.id or vals.get('unit_id')
                vals.setdefault('currency_id', schedule.currency_id.id)
                vals.setdefault('property_id', schedule.property_id.id)
            elif vals.get('lease_id') and not vals.get('currency_id'):
                lease = self.env['property.lease'].browse(vals['lease_id'])
                vals['currency_id'] = lease.currency_id.id
                vals.setdefault('property_id', lease.property_id.id)
            if not vals.get('received_amount') or vals.get('received_amount') == 0:
                vals['received_amount'] = vals.get('amount', 0.0)
        return super().create(vals_list)
