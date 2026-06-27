from odoo import api, fields, models, _


class UtilityCashierShift(models.Model):
    _name = 'utility.cashier.shift'
    _order = 'start_time desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    name = fields.Char(string='Shift Name', required=True, copy=False)
    cashier_id = fields.Many2one('res.users', string='Cashier', required=True)
    start_time = fields.Datetime(default=fields.Datetime.now, string='Start Time')
    end_time = fields.Datetime(string='End Time')
    opening_balance = fields.Monetary(string='Opening Balance')
    closing_balance = fields.Monetary(string='Closing Balance')
    expected_balance = fields.Monetary(compute='_compute_expected_balance', string='Expected Balance', store=True)
    difference = fields.Monetary(compute='_compute_difference', string='Difference', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    state = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('verified', 'Verified'),
    ], default='open', string='State', tracking=True)
    sale_ids = fields.One2many('utility.sale', 'id', string='Sales')
    total_sales = fields.Monetary(compute='_compute_totals', string='Total Sales', store=True)
    total_cash = fields.Monetary(compute='_compute_totals', string='Total Cash', store=True)
    total_pos = fields.Monetary(compute='_compute_totals', string='Total POS', store=True)
    notes = fields.Text(string='Notes')

    @api.depends('opening_balance', 'total_sales')
    def _compute_expected_balance(self):
        for rec in self:
            rec.expected_balance = (rec.opening_balance or 0.0) + (rec.total_sales or 0.0)

    @api.depends('closing_balance', 'expected_balance')
    def _compute_difference(self):
        for rec in self:
            rec.difference = (rec.closing_balance or 0.0) - (rec.expected_balance or 0.0)

    @api.depends('sale_ids', 'state')
    def _compute_totals(self):
        for rec in self:
            sales = self.env['utility.sale'].search([('operator_id', '=', rec.cashier_id.id)])
            if rec.start_time:
                sales = sales.filtered(lambda s: s.date >= rec.start_time)
            if rec.end_time and rec.state != 'open':
                sales = sales.filtered(lambda s: s.date <= rec.end_time)
            rec.total_sales = sum(sales.mapped('amount_paid'))
            rec.total_cash = sum(sales.filtered(lambda s: s.payment_method == 'cash').mapped('amount_paid'))
            rec.total_pos = sum(sales.filtered(lambda s: s.payment_method == 'pos').mapped('amount_paid'))

    def action_close(self):
        self.ensure_one()
        self.write({
            'end_time': fields.Datetime.now(),
            'state': 'closed',
        })

    def action_verify(self):
        self.ensure_one()
        self.state = 'verified'

    @api.model
    def create(self, vals):
        if not vals.get('name'):
            seq = self.env['ir.sequence'].next_by_code('utility.cashier.shift') or '/'
            vals['name'] = _('Shift %s') % seq
        return super(UtilityCashierShift, self).create(vals)
