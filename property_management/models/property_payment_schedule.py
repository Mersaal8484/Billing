from odoo import api, fields, models, _


class PropertyPaymentSchedule(models.Model):
    _name = 'property.payment.schedule'
    _description = 'Payment Schedule'
    _order = 'lease_id, sequence'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='lease_id.company_id', store=True)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    currency_id = fields.Many2one('res.currency', related='lease_id.currency_id', store=True, readonly=True)

    lease_id = fields.Many2one('property.lease', string='Lease', required=True, index=True)
    property_id = fields.Many2one('property.property', string='Property', index=True)
    unit_id = fields.Many2one('property.unit', string='Unit', index=True)
    tenant_id = fields.Many2one('property.tenant', string='Tenant', index=True)

    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Description', required=True)
    date = fields.Date(string='Due Date', required=True, index=True)
    amount = fields.Monetary(string='Amount', required=True)
    paid_amount = fields.Monetary(string='Paid Amount', compute='_compute_paid_amount', store=True)
    remaining = fields.Monetary(string='Remaining', compute='_compute_remaining', store=True)
    company_amount = fields.Monetary(string='Company Currency Amount', compute='_compute_company_amount', store=True, currency_field='company_currency_id')

    state = fields.Selection([
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ], string='Status', compute='_compute_state', store=True, index=True, tracking=True)

    payment_ids = fields.One2many('property.payment', 'schedule_id', string='Payments')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    late_fee_applied = fields.Boolean(string='Late Fee Applied', default=False)
    late_fee_amount = fields.Monetary(string='Late Fee Amount', default=0.0)

    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('check_amount_positive', 'CHECK(amount > 0)', 'Amount must be positive!'),
    ]

    @api.depends('payment_ids.state', 'payment_ids.amount', 'invoice_id.payment_state', 'invoice_id.amount_residual', 'invoice_id.amount_total')
    def _compute_paid_amount(self):
        for rec in self:
            total_paid = 0.0
            for p in rec.payment_ids:
                if p.state in ('confirmed', 'paid'):
                    if p.currency_id != rec.currency_id:
                        try:
                            total_paid += p.currency_id._convert(p.amount, rec.currency_id, rec.company_id, p.date)
                        except Exception:
                            total_paid += p.amount
                    else:
                        total_paid += p.amount
            if rec.invoice_id:
                if rec.invoice_id.payment_state in ('paid', 'in_payment'):
                    total_paid = rec.amount
                elif rec.invoice_id.payment_state == 'partial':
                    invoice_paid = rec.invoice_id.amount_total - rec.invoice_id.amount_residual
                    if rec.invoice_id.currency_id != rec.currency_id:
                        try:
                            invoice_paid = rec.invoice_id.currency_id._convert(invoice_paid, rec.currency_id, rec.company_id, rec.invoice_id.invoice_date or fields.Date.today())
                        except Exception:
                            pass
                    if invoice_paid > total_paid:
                        total_paid = invoice_paid
            rec.paid_amount = total_paid

    @api.depends('paid_amount', 'amount', 'date')
    def _compute_state(self):
        today = fields.Date.today()
        for rec in self:
            if rec.paid_amount >= rec.amount:
                rec.state = 'paid'
            elif rec.paid_amount > 0:
                rec.state = 'partial'
            elif rec.date and rec.date < today:
                rec.state = 'overdue'
            else:
                rec.state = 'pending'

    @api.depends('amount', 'paid_amount')
    def _compute_remaining(self):
        for rec in self:
            rec.remaining = rec.amount - rec.paid_amount

    @api.depends('amount', 'currency_id')
    def _compute_company_amount(self):
        for rec in self:
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

    def action_register_payment(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Register Payment'),
            'res_model': 'property.payment',
            'view_mode': 'form',
            'context': {
                'default_schedule_id': self.id,
                'default_lease_id': self.lease_id.id,
                'default_tenant_id': self.tenant_id.id,
                'default_unit_id': self.unit_id.id,
                'default_amount': self.remaining,
                'default_date': fields.Date.today(),
            },
            'target': 'new',
        }

    def action_generate_invoice(self):
        self.ensure_one()
        property_rec = self.lease_id.property_id
        income_account = property_rec._get_rent_income_account() if property_rec else self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        journal = property_rec._get_journal_for_method('rent') if property_rec else self.env['account.journal'].search([
            ('company_id', '=', self.company_id.id),
            ('type', '=', 'sale'),
        ], limit=1)
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.tenant_id.partner_id.id,
            'invoice_date': fields.Date.today(),
            'currency_id': self.currency_id.id,
            'journal_id': journal.id if journal else False,
            'invoice_line_ids': [(0, 0, {
                'name': self.name,
                'quantity': 1.0,
                'price_unit': self.amount,
                'account_id': income_account.id,
                'analytic_distribution': {str(self.unit_id.analytic_account_id.id): 100.0} if self.unit_id and self.unit_id.analytic_account_id else False,
            })],
        })
        self.invoice_id = invoice.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        }

    @api.model
    def cron_update_overdue(self):
        today = fields.Date.today()
        overdue = self.search([
            ('date', '<', today),
            ('state', 'in', ('pending', 'partial')),
        ])
        overdue.write({'state': 'overdue'})

        for schedule in overdue:
            if not schedule.late_fee_applied and schedule.lease_id and (schedule.lease_id.late_fee_percent > 0 or schedule.lease_id.late_fee_fixed > 0):
                grace_period = schedule.lease_id.grace_period or 0
                if (today - schedule.date).days > grace_period:
                    penalty = schedule.lease_id.late_fee_fixed + (schedule.amount * (schedule.lease_id.late_fee_percent / 100.0))
                    if penalty > 0:
                        schedule.late_fee_applied = True
                        schedule.late_fee_amount = penalty

                        property_rec = schedule.property_id
                        income_account = property_rec._get_service_income_account() if property_rec else self.env['account.account'].search([
                            ('account_type', '=', 'income'),
                            ('company_id', '=', schedule.company_id.id),
                        ], limit=1)
                        journal = property_rec._get_journal_for_method('rent') if property_rec else self.env['account.journal'].search([
                            ('company_id', '=', schedule.company_id.id),
                            ('type', '=', 'sale'),
                        ], limit=1)

                        invoice = self.env['account.move'].create({
                            'move_type': 'out_invoice',
                            'partner_id': schedule.tenant_id.partner_id.id,
                            'invoice_date': today,
                            'currency_id': schedule.currency_id.id,
                            'journal_id': journal.id if journal else False,
                            'invoice_line_ids': [(0, 0, {
                                'name': f'Late Fee Penalty - {schedule.name}',
                                'quantity': 1.0,
                                'price_unit': penalty,
                                'account_id': income_account.id,
                                'analytic_distribution': {str(schedule.unit_id.analytic_account_id.id): 100.0} if schedule.unit_id and schedule.unit_id.analytic_account_id else False,
                            })],
                        })

                        self.env['property.payment'].create({
                            'name': f'Late Fee - {schedule.name}',
                            'schedule_id': schedule.id,
                            'lease_id': schedule.lease_id.id,
                            'tenant_id': schedule.tenant_id.id,
                            'unit_id': schedule.unit_id.id,
                            'property_id': schedule.property_id.id,
                            'amount': penalty,
                            'currency_id': schedule.currency_id.id,
                            'payment_type': 'late_fee',
                            'payment_method': 'bank_transfer',
                            'date': today,
                            'state': 'confirmed',
                            'invoice_id': invoice.id,
                            'notes': f'Automated late fee penalty generated on {today}.',
                        })
