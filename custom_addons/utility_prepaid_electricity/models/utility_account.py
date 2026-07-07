from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityAccount(models.Model):
    _name = 'utility.account'
    _description = 'Utility Account'
    _order = 'account_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'account_number'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    account_number = fields.Char(string='Account Number', required=True, index=True, copy=False,
                                 default=lambda self: _('New'))
    customer_id = fields.Many2one('utility.customer', string='Customer', required=True, index=True, tracking=True)
    meter_id = fields.Many2one('utility.meter', string='Meter', index=True, tracking=True)
    tariff_id = fields.Many2one('utility.tariff', string='Tariff', required=True, index=True, tracking=True)

    balance = fields.Monetary(string='Current Balance', default=0.0, digits=(16, 4), tracking=True)
    emergency_credit = fields.Monetary(string='Emergency Credit', default=0.0, digits=(16, 4))
    emergency_credit_used = fields.Monetary(string='Emergency Credit Used', default=0.0, digits=(16, 4))
    available_emergency_credit = fields.Monetary(string='Available Emergency Credit',
                                                 compute='_compute_available_emergency', store=True, digits=(16, 4))
    debt_amount = fields.Monetary(string='Outstanding Debt', default=0.0, digits=(16, 4))

    total_purchases = fields.Monetary(string='Total Purchases (Lifetime)', default=0.0, digits=(16, 4))
    total_kwh_purchased = fields.Float(string='Total kWh Purchased', default=0.0, digits=(16, 2))
    last_purchase_date = fields.Datetime(string='Last Purchase Date')
    last_token_date = fields.Datetime(string='Last Token Date')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('disconnected', 'Disconnected'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', index=True, tracking=True, required=True)

    region_id = fields.Many2one('utility.region', related='customer_id.region_id', store=True, index=True)
    area_id = fields.Many2one('utility.area', related='customer_id.area_id', store=True, index=True)

    sale_ids = fields.One2many('utility.sale', 'account_id', string='Sales')
    transaction_ids = fields.One2many('utility.transaction', 'account_id', string='Transactions')
    adjustment_ids = fields.One2many('utility.adjustment', 'account_id', string='Adjustments')
    alarm_ids = fields.One2many('utility.alarm', 'account_id', string='Alarms')

    sale_count = fields.Integer(string='Sale Count', compute='_compute_sale_count', store=True)
    last_sale_id = fields.Many2one('utility.sale', string='Last Sale', compute='_compute_last_sale', store=True)

    _sql_constraints = [
        ('account_number_uniq', 'UNIQUE(account_number, company_id)', 'Account number must be unique per company!'),
    ]

    @api.depends('emergency_credit', 'emergency_credit_used')
    def _compute_available_emergency(self):
        for rec in self:
            rec.available_emergency_credit = max(0.0, rec.emergency_credit - rec.emergency_credit_used)

    @api.depends('sale_ids')
    def _compute_sale_count(self):
        for rec in self:
            rec.sale_count = len(rec.sale_ids)

    @api.depends('sale_ids', 'sale_ids.date')
    def _compute_last_sale(self):
        for rec in self:
            last = rec.sale_ids.sorted('date', reverse=True)[:1]
            rec.last_sale_id = last.id if last else False

    def action_set_active(self):
        self.write({'state': 'active'})

    def action_suspend(self):
        self.write({'state': 'suspended'})

    def action_disconnect(self):
        self.write({'state': 'disconnected'})

    def action_close(self):
        self.write({'state': 'closed'})

    @api.model
    def create(self, vals):
        if vals.get('account_number', _('New')) == _('New'):
            vals['account_number'] = self.env['ir.sequence'].next_by_code('utility.account') or _('New')
        return super().create(vals)

    def name_get(self):
        return [(rec.id, rec.account_number) for rec in self]
