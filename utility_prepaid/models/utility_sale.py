from odoo import api, fields, models, _


class UtilitySale(models.Model):
    _name = 'utility.sale'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    receipt_number = fields.Char(required=True, index=True, default=lambda self: _('New'))
    date = fields.Datetime(default=fields.Datetime.now)
    customer_id = fields.Many2one('res.partner', string='Customer', required=True, index=True)
    account_id = fields.Many2one('utility.customer', string='Account', required=True, index=True)
    meter_id = fields.Many2one('utility.meter', string='Meter', index=True)
    tariff_id = fields.Many2one('utility.tariff', string='Tariff', index=True)
    amount_paid = fields.Monetary(string='Amount Paid', required=True)
    kwh_purchased = fields.Float(string='kWh Purchased')
    unit_price = fields.Float(string='Unit Price')
    energy_charge = fields.Monetary(string='Energy Charge')
    fixed_charge = fields.Monetary(string='Fixed Charge')
    service_charge = fields.Monetary(string='Service Charge')
    fuel_adjustment = fields.Monetary(string='Fuel Adjustment')
    tax_amount = fields.Monetary(string='Tax Amount')
    total_charge = fields.Monetary(string='Total Charge')
    balance_before = fields.Monetary(string='Balance Before')
    balance_after = fields.Monetary(compute='_compute_balance_after', string='Balance After', store=True)
    line_ids = fields.One2many('utility.sale.line', 'sale_id', string='Sale Lines')
    token_id = fields.Many2one('utility.token', string='Token')
    payment_id = fields.Many2one('utility.payment', string='Payment')
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('pos', 'POS Terminal'),
        ('bank', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('wallet', 'Digital Wallet'),
        ('online', 'Online Payment'),
    ], string='Payment Method')
    payment_reference = fields.Char(string='Payment Reference')
    reference_number = fields.Char(string='Reference Number')
    operator_id = fields.Many2one('res.users', string='Operator', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('token_generated', 'Token Generated'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('reversed', 'Reversed'),
    ], default='draft', string='State', tracking=True)
    token_status = fields.Selection([
        ('pending', 'Pending'),
        ('generated', 'Generated'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Token Status', default='pending')
    sms_sent = fields.Boolean(string='SMS Sent')
    printed = fields.Boolean(string='Printed')
    notes = fields.Text(string='Notes')
    reversal_id = fields.Many2one('utility.reversal', string='Reversal')

    _sql_constraints = [
        ('unique_receipt_number_company', 'unique(receipt_number, company_id)',
         'Receipt number must be unique per company!'),
    ]

    @api.depends('amount_paid', 'balance_before')
    def _compute_balance_after(self):
        for rec in self:
            rec.balance_after = (rec.balance_before or 0.0) + (rec.amount_paid or 0.0)

    def action_calculate(self):
        self.ensure_one()
        if not self.tariff_id or not self.amount_paid:
            return
        result = self.tariff_id.calculate_kwh(self.amount_paid)
        self.kwh_purchased = result.get('kwh', 0.0)
        self.unit_price = result.get('unit_price', 0.0)
        self.energy_charge = result.get('energy_charge', 0.0)
        self.fixed_charge = result.get('fixed_charge', 0.0)
        self.service_charge = result.get('service_charge', 0.0)
        self.fuel_adjustment = result.get('fuel_adjustment', 0.0)
        self.tax_amount = result.get('tax_amount', 0.0)
        self.total_charge = result.get('total_charge', self.amount_paid)
        self.balance_before = self.account_id.balance if self.account_id else 0.0

    def action_confirm(self):
        self.ensure_one()
        if not self.receipt_number or self.receipt_number == _('New'):
            self.receipt_number = self.env['ir.sequence'].next_by_code('utility.sale') or _('New')
        if not self.amount_paid or self.amount_paid <= 0:
            raise models.ValidationError(_('Amount paid must be greater than zero.'))
        self.action_calculate()
        self.state = 'confirmed'

    def action_generate_token(self):
        self.ensure_one()
        token = self.env['utility.token'].create({
            'sale_id': self.id,
            'account_id': self.account_id.id,
            'meter_id': self.meter_id.id,
            'customer_id': self.customer_id.id,
            'tariff_id': self.tariff_id.id,
            'amount': self.amount_paid,
            'kwh': self.kwh_purchased,
        })
        token.action_request_token()
        self.token_id = token.id
        if token.status == 'success':
            self.token_status = 'generated'
            self.state = 'token_generated'
        else:
            self.token_status = 'failed'

    def action_complete(self):
        self.ensure_one()
        self.account_id._update_balance(self.amount_paid)
        self.balance_before = self.account_id.balance - self.amount_paid
        self.balance_after = self.account_id.balance
        self.env['utility.transaction'].create_transaction(
            'sale', self.account_id, self.amount_paid, sale=self,
            notes=_('Prepaid sale completed: %s') % self.receipt_number,
        )
        self.state = 'completed'

    def action_cancel(self):
        self.ensure_one()
        if self.token_id and self.token_id.status == 'success':
            self.token_id.action_cancel()
        self.state = 'cancelled'

    @api.model
    def create(self, vals):
        if vals.get('receipt_number', _('New')) == _('New'):
            vals['receipt_number'] = self.env['ir.sequence'].next_by_code('utility.sale') or _('New')
        return super(UtilitySale, self).create(vals)
