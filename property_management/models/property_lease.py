from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta


class PropertyLease(models.Model):
    _name = 'property.lease'
    _description = 'Lease Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='property_id.company_id', store=True, index=True)
    currency_id = fields.Many2one('res.currency', string='Contract Currency', required=True, default=lambda self: self.env.company.currency_id)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    name = fields.Char(string='Lease Reference', required=True, index=True,
                       default=lambda self: _('New'))
    property_id = fields.Many2one('property.property', string='Property',
                                  required=True, index=True, tracking=True)
    building_id = fields.Many2one('property.building', string='Building',
                                  related='unit_id.building_id', store=True)
    unit_id = fields.Many2one('property.unit', string='Unit', required=True,
                              index=True, tracking=True)

    tenant_id = fields.Many2one('property.tenant', string='Tenant', required=True,
                                tracking=True, index=True)
    owner_id = fields.Many2one('property.owner', string='Owner',
                               related='unit_id.owner_id', store=True)

    lease_type = fields.Selection([
        ('new', 'New Lease'),
        ('renewal', 'Renewal'),
        ('extension', 'Extension'),
    ], string='Lease Type', default='new', tracking=True)

    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)
    duration_months = fields.Integer(string='Duration (Months)',
                                     compute='_compute_duration', store=True)
    notice_period = fields.Integer(string='Notice Period (Days)', default=30)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('renewed', 'Renewed'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    rent_amount = fields.Monetary(string='Rent Amount', required=True, tracking=True)
    rent_frequency = fields.Many2one('property.payment.frequency',
                                     string='Payment Frequency', required=True)
    annual_rent = fields.Monetary(string='Annual Rent',
                                  compute='_compute_annual_rent', store=True)
    total_contract_value = fields.Monetary(string='Total Contract Value',
                                           compute='_compute_annual_rent', store=True)

    security_deposit = fields.Monetary(string='Security Deposit', default=0.0,
                                       compute='_compute_security_deposit', store=True, readonly=False)
    deposit_months = fields.Integer(string='Deposit (Months)', default=1)
    deposit_id = fields.Many2one('property.deposit', string='Deposit Record')

    escalation_percent = fields.Float(string='Annual Escalation %', default=0.0,
                                      digits=(5, 2))
    escalation_frequency = fields.Selection([
        ('annual', 'Annual'),
        ('biannual', 'Bi-Annual'),
    ], string='Escalation Frequency', default='annual')

    grace_period = fields.Integer(string='Grace Period (Days)', default=0)
    late_fee_percent = fields.Float(string='Late Fee %', default=0.0, digits=(5, 2))
    late_fee_fixed = fields.Monetary(string='Late Fee Fixed Amount', default=0.0)

    renewal_option = fields.Boolean(string='Renewal Option', default=False)
    renewal_notice_days = fields.Integer(string='Renewal Notice (Days)', default=60)

    line_ids = fields.One2many('property.lease.line', 'lease_id',
                               string='Lease Terms & Conditions', copy=True)
    schedule_ids = fields.One2many('property.payment.schedule', 'lease_id',
                                   string='Payment Schedule')
    payment_ids = fields.One2many('property.payment', 'lease_id',
                                  string='Payments')

    total_paid = fields.Monetary(string='Total Paid',
                                 compute='_compute_payment_summary', store=True)
    total_due = fields.Monetary(string='Total Due',
                                compute='_compute_payment_summary', store=True)
    balance_due = fields.Monetary(string='Balance Due',
                                  compute='_compute_payment_summary', store=True)
    last_payment_date = fields.Date(string='Last Payment Date',
                                    compute='_compute_payment_summary', store=True)

    approved_by = fields.Many2one('res.users', string='Approved By', tracking=True)
    approved_date = fields.Date(string='Approval Date')
    closed_date = fields.Date(string='Closed Date')
    close_reason = fields.Text(string='Close Reason')

    term_conditions = fields.Html(string='Terms & Conditions')
    notes = fields.Text(string='Notes')
    internal_notes = fields.Text(string='Internal Notes')

    _sql_constraints = [
        ('check_dates', 'CHECK(start_date <= end_date)',
         'Start date must be before end date!'),
        ('check_rent_positive', 'CHECK(rent_amount > 0)',
         'Rent amount must be positive!'),
    ]

    @api.depends('unit_id', 'rent_amount', 'deposit_months')
    def _compute_security_deposit(self):
        for rec in self:
            if rec.unit_id and rec.unit_id.security_deposit:
                rec.security_deposit = rec.unit_id.security_deposit
            elif rec.rent_amount and rec.deposit_months:
                rec.security_deposit = rec.rent_amount * rec.deposit_months
            else:
                rec.security_deposit = rec.security_deposit or 0.0

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                # Add 1 day to end_date to make it inclusive (e.g. Jan 1 to Dec 31 becomes exactly 1 year / 12 months)
                delta = relativedelta(rec.end_date + relativedelta(days=1), rec.start_date)
                rec.duration_months = delta.years * 12 + delta.months
            else:
                rec.duration_months = 0

    @api.depends('rent_amount', 'rent_frequency')
    def _compute_annual_rent(self):
        for rec in self:
            if rec.rent_frequency and rec.rent_amount:
                code = (rec.rent_frequency.code or '').upper()
                if code == 'MONTHLY':
                    payments_per_year = 12.0
                elif code == 'QUARTERLY':
                    payments_per_year = 4.0
                elif code == 'SEMI':
                    payments_per_year = 2.0
                elif code == 'ANNUAL':
                    payments_per_year = 1.0
                else:
                    freq_days = rec.rent_frequency.days or 30
                    payments_per_year = 360.0 / freq_days if freq_days else 12.0
                rec.annual_rent = rec.rent_amount * payments_per_year
            else:
                rec.annual_rent = rec.rent_amount or 0.0
            rec.total_contract_value = rec.annual_rent * (rec.duration_months / 12.0) if rec.duration_months else rec.annual_rent

    @api.depends('schedule_ids', 'schedule_ids.amount', 'schedule_ids.remaining', 'schedule_ids.state', 'payment_ids.amount', 'payment_ids.currency_id', 'payment_ids.date', 'payment_ids.state')
    def _compute_payment_summary(self):
        for rec in self:
            paid_total = 0.0
            for payment in rec.payment_ids.filtered(lambda p: p.state == 'paid' and p.schedule_id):
                payment_currency = payment.currency_id or rec.currency_id
                payment_date = payment.date or fields.Date.context_today(self)
                try:
                    paid_total += payment_currency._convert(payment.amount, rec.currency_id, rec.company_id, payment_date)
                except Exception:
                    paid_total += payment.amount
            rec.total_paid = paid_total
            rec.total_due = sum(rec.schedule_ids.mapped('remaining'))
            rec.balance_due = rec.total_due
            paid = rec.payment_ids.filtered(lambda p: p.state == 'paid' and p.schedule_id)
            rec.last_payment_date = paid.sorted('date')[-1:].date if paid else False

    def action_review(self):
        self.write({'state': 'review'})

    def action_activate(self):
        if not self.schedule_ids:
            self.action_generate_schedule()
        self.unit_id.write({
            'status': self.env.ref('property_management.unit_status_occupied',
                                   raise_if_not_found=False).id or False,
            'current_tenant_id': self.tenant_id.id,
            'current_lease_id': self.id,
        })
        deposit_amount = self.security_deposit
        if deposit_amount > 0 and not self.deposit_id:
            deposit = self.env['property.deposit'].create({
                'lease_id': self.id,
                'tenant_id': self.tenant_id.id,
                'unit_id': self.unit_id.id,
                'amount': deposit_amount,
                'date_received': fields.Date.today(),
            })
            self.deposit_id = deposit.id
            deposit_payment = self.env['property.payment'].create({
                'lease_id': self.id,
                'tenant_id': self.tenant_id.id,
                'unit_id': self.unit_id.id,
                'property_id': self.property_id.id,
                'amount': deposit_amount,
                'currency_id': self.currency_id.id,
                'payment_type': 'deposit',
                'payment_method': 'cash',
                'date': fields.Date.today(),
                'state': 'confirmed',
                'reference': deposit.name,
                'journal_id': self.property_id._get_journal_for_method('deposit').id,
            })
            deposit_payment.action_paid()
            deposit.receipt_payment_id = deposit_payment.id
        self.write({
            'state': 'active',
            'approved_by': self.env.user.id,
            'approved_date': fields.Date.today(),
        })

    def action_expire(self):
        self.write({'state': 'expired'})
        self.unit_id.write({
            'status': self.env.ref('property_management.unit_status_available',
                                   raise_if_not_found=False).id or False,
            'current_tenant_id': False,
            'current_lease_id': False,
        })

    def action_renew(self):
        new_lease = self.copy({
            'name': _('New'),
            'state': 'draft',
            'lease_type': 'renewal',
            'start_date': self.end_date,
            'end_date': self.end_date + relativedelta(months=self.duration_months or 12),
            'schedule_ids': False,
            'payment_ids': False,
        })
        self.write({'state': 'renewed'})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Renewed Lease'),
            'res_model': 'property.lease',
            'view_mode': 'form',
            'res_id': new_lease.id,
        }

    def action_close(self):
        self.write({
            'state': 'closed',
            'closed_date': fields.Date.today(),
        })
        self.unit_id.write({
            'status': self.env.ref('property_management.unit_status_available',
                                   raise_if_not_found=False).id or False,
            'current_tenant_id': False,
            'current_lease_id': False,
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_generate_schedule(self):
        self.ensure_one()
        existing = self.env['property.payment.schedule'].search([('lease_id', '=', self.id)])
        if existing:
            existing.unlink()
        if not self.rent_frequency:
            raise UserError(_('Please select a payment frequency first!'))
        
        freq_code = (self.rent_frequency.code or '').upper()
        if freq_code == 'MONTHLY':
            delta = relativedelta(months=1)
        elif freq_code == 'QUARTERLY':
            delta = relativedelta(months=3)
        elif freq_code == 'SEMI':
            delta = relativedelta(months=6)
        elif freq_code == 'ANNUAL':
            delta = relativedelta(years=1)
        else:
            freq_days = self.rent_frequency.days or 30
            delta = relativedelta(days=freq_days)

        current_date = self.start_date
        seq = 1
        while current_date < self.end_date:
            amount = self.rent_amount
            year = current_date.year - self.start_date.year
            if self.escalation_percent and year > 0:
                amount *= (1 + self.escalation_percent / 100) ** year
            
            next_date = current_date + delta
            due_date = min(next_date - relativedelta(days=1), self.end_date)
            
            # Pro-rata for final partial period if shorter than standard frequency period
            total_days = (next_date - current_date).days
            actual_days = (due_date - current_date).days + 1
            if actual_days < total_days and due_date == self.end_date:
                amount = (amount / total_days) * actual_days
                
            self.env['property.payment.schedule'].create({
                'lease_id': self.id,
                'tenant_id': self.tenant_id.id,
                'unit_id': self.unit_id.id,
                'property_id': self.property_id.id,
                'sequence': seq,
                'name': f'{self.name} - Payment #{seq}',
                'date': due_date,
                'amount': amount,
                'state': 'pending',
            })
            seq += 1
            current_date = next_date

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                seq = self.env['ir.sequence'].next_by_code('property.lease')
                vals['name'] = seq or '/'
            vals.setdefault('currency_id', self.env.company.currency_id.id)
        return super().create(vals_list)


class PropertyLeaseLine(models.Model):
    _name = 'property.lease.line'
    _description = 'Lease Clause/Term'

    lease_id = fields.Many2one('property.lease', string='Lease', required=True,
                               ondelete='cascade')
    sequence = fields.Integer(default=10)
    title = fields.Char(string='Title', required=True)
    content = fields.Text(string='Content', required=True)


class PropertyLeaseStatus(models.Model):
    _name = 'property.lease.status'
    _description = 'Lease Status'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)


class PropertyPaymentFrequency(models.Model):
    _name = 'property.payment.frequency'
    _description = 'Payment Frequency'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    days = fields.Integer(string='Days', required=True, default=30)
    sequence = fields.Integer(default=10)
