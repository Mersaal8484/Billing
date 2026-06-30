from odoo import api, fields, models, _


class UtilityCashierShift(models.Model):
    _name = 'utility.cashier.shift'
    _description = 'Utility Cashier Shift'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_time desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    name = fields.Char(string='اسم الوردية', required=True, copy=False)
    cashier_id = fields.Many2one('res.users', string='الكاشير',
        default=lambda self: self.env.user)
    start_time = fields.Datetime(default=fields.Datetime.now, string='وقت البداية')
    end_time = fields.Datetime(string='وقت النهاية')
    opening_balance = fields.Monetary(string='الرصيد الافتتاحي')
    closing_balance = fields.Monetary(string='الرصيد الختامي')
    expected_balance = fields.Monetary(compute='_compute_expected_balance', string='الرصيد المتوقع', store=True)
    difference = fields.Monetary(compute='_compute_difference', string='الفرق', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    state = fields.Selection([
        ('open', 'مفتوحة'),
        ('closed', 'مغلقة'),
        ('verified', 'مدققة'),
    ], default='open', string='الحالة', tracking=True)

    total_sales = fields.Monetary(compute='_compute_pos_data', string='إجمالي مبيعات POS', store=True)
    total_cash = fields.Monetary(compute='_compute_pos_data', string='نقدي', store=True)
    notes = fields.Text(string='ملاحظات')

    @api.depends('start_time', 'end_time', 'state')
    def _compute_pos_data(self):
        for rec in self:
            user = rec.cashier_id
            if not user:
                rec.total_sales = 0.0
                rec.total_cash = 0.0
                continue
            orders = self.env['pos.order'].search([
                ('user_id', '=', user.id),
            ])
            if rec.start_time:
                orders = orders.filtered(lambda o: o.date_order >= rec.start_time)
            if rec.end_time and rec.state != 'open':
                orders = orders.filtered(lambda o: o.date_order <= rec.end_time)
            rec.total_sales = sum(orders.mapped('amount_paid'))
            rec.total_cash = rec.total_sales

    @api.depends('opening_balance', 'total_sales')
    def _compute_expected_balance(self):
        for rec in self:
            rec.expected_balance = (rec.opening_balance or 0.0) + (rec.total_sales or 0.0)

    @api.depends('closing_balance', 'expected_balance')
    def _compute_difference(self):
        for rec in self:
            rec.difference = (rec.closing_balance or 0.0) - (rec.expected_balance or 0.0)

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
            vals['name'] = _('وردية %s') % seq
        return super(UtilityCashierShift, self).create(vals)
