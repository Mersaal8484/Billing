from odoo import api, fields, models, _

class UtilityCollectorShift(models.Model):
    _name = 'utility.collector.shift'
    _description = 'Utility Collector Shift'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_time desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    name = fields.Char(string='اسم يومية التحصيل', required=True, copy=False)
    collector_id = fields.Many2one('res.users', string='المتحصل الميداني',
        default=lambda self: self.env.user, domain=lambda self: [('groups_id', 'in', self.env.ref('utility_core.group_utility_collector').id)])
    route_id = fields.Many2one('utility.route', string='المسار')
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

    payment_ids = fields.One2many('account.payment', 'collector_shift_id', string='المدفوعات المحصلة')
    total_collected = fields.Monetary(compute='_compute_collections', string='إجمالي التحصيل', store=True)
    notes = fields.Text(string='ملاحظات')

    @api.depends('payment_ids.amount', 'payment_ids.state')
    def _compute_collections(self):
        for rec in self:
            rec.total_collected = sum(
                rec.payment_ids.filtered(lambda p: p.state == 'posted').mapped('amount')
            )

    @api.depends('opening_balance', 'total_collected')
    def _compute_expected_balance(self):
        for rec in self:
            rec.expected_balance = (rec.opening_balance or 0.0) + (rec.total_collected or 0.0)

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
            seq = self.env['ir.sequence'].next_by_code('utility.collector.shift') or '/'
            vals['name'] = _('يومية تحصيل %s') % seq
        return super(UtilityCollectorShift, self).create(vals)
