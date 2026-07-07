from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class UtilitySale(models.Model):
    _name = 'utility.sale'
    _description = 'Prepaid Electricity Sale'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'receipt_number'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    receipt_number = fields.Char(string='Receipt Number', required=True, index=True, copy=False,
                                 default=lambda self: _('New'))
    date = fields.Datetime(string='Sale Date', default=fields.Datetime.now, required=True, index=True)

    customer_id = fields.Many2one('utility.customer', string='Customer', required=True, index=True, tracking=True)
    account_id = fields.Many2one('utility.account', string='Account', required=True, index=True, tracking=True)
    meter_id = fields.Many2one('utility.meter', string='Meter', required=True, index=True, tracking=True)
    tariff_id = fields.Many2one('utility.tariff', string='Tariff', required=True, tracking=True)

    region_id = fields.Many2one('utility.region', related='customer_id.region_id', store=True, index=True)
    area_id = fields.Many2one('utility.area', related='customer_id.area_id', store=True, index=True)

    amount_paid = fields.Monetary(string='Amount Paid', required=True, digits=(16, 4))
    kwh_purchased = fields.Float(string='kWh Purchased', digits=(16, 2), readonly=True)
    unit_price = fields.Monetary(string='Unit Price', digits=(16, 6), readonly=True)
    energy_charge = fields.Monetary(string='Energy Charge', readonly=True, digits=(16, 4))
    fixed_charge = fields.Monetary(string='Fixed Charge', readonly=True)
    service_charge = fields.Monetary(string='Service Charge', readonly=True)
    fuel_adjustment = fields.Monetary(string='Fuel Adjustment', readonly=True)
    tax_amount = fields.Monetary(string='Tax Amount', readonly=True)
    total_charge = fields.Monetary(string='Total Charges', readonly=True, digits=(16, 4))

    balance_before = fields.Monetary(string='Balance Before', readonly=True, digits=(16, 4))
    balance_after = fields.Monetary(string='Balance After', compute='_compute_balance_after', store=True, digits=(16, 4))

    line_ids = fields.One2many('utility.sale.line', 'sale_id', string='Sale Lines', copy=False)

    token_id = fields.Many2one('utility.token', string='STS Token', readonly=True, copy=False)
    token_status = fields.Selection([
        ('pending', 'Pending'),
        ('generated', 'Token Generated'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Token Status', default='pending', readonly=True, tracking=True)

    payment_id = fields.Many2one('utility.payment', string='Payment', readonly=True, copy=False)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('pos', 'POS Terminal'),
        ('bank', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('wallet', 'Digital Wallet'),
        ('online', 'Online Payment'),
    ], string='Payment Method', default='cash', required=True, tracking=True)
    payment_reference = fields.Char(string='Payment Reference')

    operator_id = fields.Many2one('res.users', string='Operator', default=lambda self: self.env.user,
                                  required=True, index=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('token_generated', 'Token Generated'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('reversed', 'Reversed'),
    ], string='Status', default='draft', index=True, tracking=True, required=True)

    notes = fields.Text(string='Notes')
    sms_sent = fields.Boolean(string='SMS Sent', default=False)
    printed = fields.Boolean(string='Receipt Printed', default=False)

    reversal_id = fields.Many2one('utility.reversal', string='Reversal', readonly=True, copy=False)
    is_reversed = fields.Boolean(string='Is Reversed', compute='_compute_is_reversed', store=True)

    _sql_constraints = [
        ('receipt_number_uniq', 'UNIQUE(receipt_number, company_id)', 'Receipt number must be unique!'),
        ('check_amount_positive', 'CHECK(amount_paid > 0)', 'Amount must be positive!'),
    ]

    @api.depends('balance_before', 'kwh_purchased', 'total_charge')
    def _compute_balance_after(self):
        for rec in self:
            rec.balance_after = (rec.balance_before or 0.0) + rec.kwh_purchased

    @api.depends('reversal_id')
    def _compute_is_reversed(self):
        for rec in self:
            rec.is_reversed = bool(rec.reversal_id)

    def action_calculate(self):
        """Calculate kWh and charges based on tariff."""
        self.ensure_one()
        if not self.tariff_id:
            raise UserError(_('Please select a tariff first.'))
        if not self.amount_paid or self.amount_paid <= 0:
            raise UserError(_('Please enter a valid amount.'))

        self.balance_before = self.account_id.balance
        result = self.tariff_id.calculate_kwh(self.amount_paid, self.date)
        self.write({
            'kwh_purchased': result['kwh'],
            'unit_price': result['unit_price'],
            'energy_charge': result['energy_charge'],
            'fixed_charge': result['fixed_charge'],
            'service_charge': result['service_charge'],
            'fuel_adjustment': result['fuel_adjustment'],
            'tax_amount': result['tax'],
            'total_charge': result['total'],
        })

    def action_confirm(self):
        """Confirm sale and trigger token generation."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Sale can only be confirmed from draft state.'))
        if self.kwh_purchased <= 0:
            self.action_calculate()
        if self.kwh_purchased <= 0:
            raise UserError(_('Calculated kWh must be greater than zero.'))
        self.write({
            'state': 'confirmed',
            'balance_before': self.account_id.balance,
        })

    def action_generate_token(self):
        """Generate STS token via pluggable integration."""
        self.ensure_one()
        if self.state not in ('confirmed', 'draft'):
            raise UserError(_('Token generation requires confirmed state.'))
        if self.state == 'draft':
            self.action_confirm()
        token_vals = {
            'sale_id': self.id,
            'account_id': self.account_id.id,
            'meter_id': self.meter_id.id,
            'customer_id': self.customer_id.id,
            'amount': self.amount_paid,
            'kwh': self.kwh_purchased,
            'tariff_id': self.tariff_id.id,
        }
        # Pluggable STS integration point - calls external vending server
        # In production, this would call an external STS vending system
        token = self.env['utility.token'].create(token_vals)
        token.action_request_token()
        self.write({
            'token_id': token.id,
            'token_status': 'generated',
            'state': 'token_generated',
        })

    def action_complete(self):
        """Complete the sale and update balances."""
        self.ensure_one()
        if self.state != 'token_generated':
            raise UserError(_('Sale must have a generated token before completion.'))
        self.account_id.write({
            'balance': self.balance_after,
            'total_purchases': self.account_id.total_purchases + self.amount_paid,
            'total_kwh_purchased': self.account_id.total_kwh_purchased + self.kwh_purchased,
            'last_purchase_date': fields.Datetime.now(),
        })
        self.write({'state': 'completed'})
        self._create_audit('sale', f'Sale completed: {self.receipt_number}')

    def action_cancel(self):
        self.write({'state': 'cancelled', 'token_status': 'cancelled'})

    def action_reverse(self):
        """Reverse this sale via supervisor approval."""
        if not self.env.user.has_group('utility_prepaid_electricity.group_utility_supervisor'):
            raise UserError(_('Only supervisors can reverse sales.'))
        return {
            'name': _('Reverse Sale'),
            'type': 'ir.actions.act_window',
            'res_model': 'utility.reversal',
            'view_mode': 'form',
            'context': {
                'default_sale_id': self.id,
                'default_account_id': self.account_id.id,
                'default_customer_id': self.customer_id.id,
                'default_meter_id': self.meter_id.id,
                'default_amount': self.amount_paid,
                'default_reason': 'Sale reversal',
            },
        }

    def action_send_sms(self):
        """Send token via SMS (pluggable SMS gateway integration)."""
        self.ensure_one()
        if not self.token_id or not self.token_id.token_number:
            raise UserError(_('No token available to send.'))
        mobile = self.customer_id.mobile
        if not mobile:
            raise UserError(_('Customer has no mobile number registered.'))
        # Pluggable SMS gateway integration point
        self.sms_sent = True
        return True

    def _create_audit(self, action, description):
        self.env['utility.audit'].create({
            'model': 'utility.sale',
            'res_id': self.id,
            'action': action,
            'description': description,
            'user_id': self.env.user.id,
        })

    @api.model
    def create(self, vals):
        if vals.get('receipt_number', _('New')) == _('New'):
            vals['receipt_number'] = self.env['ir.sequence'].next_by_code('utility.sale') or _('New')
        return super().create(vals)
