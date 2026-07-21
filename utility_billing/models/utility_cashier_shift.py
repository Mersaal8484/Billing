import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UtilityCashierShift(models.Model):
    _name = 'utility.cashier.shift'
    _description = 'وردية كاشير'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_time desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company, index=True)
    name = fields.Char('اسم الوردية', required=True, copy=False, default=lambda self: _('جديد'))
    cashier_id = fields.Many2one('res.users', 'الكاشير',
        default=lambda self: self.env.user, required=True, index=True)
    start_time = fields.Datetime('وقت البداية', default=fields.Datetime.now)
    end_time = fields.Datetime('وقت النهاية')
    opening_balance = fields.Monetary('الرصيد الافتتاحي', currency_field='currency_id')
    closing_balance = fields.Monetary('الرصيد الختامي', currency_field='currency_id')
    expected_balance = fields.Monetary('الرصيد المتوقع', compute='_compute_expected_balance',
        currency_field='currency_id', store=True)
    difference = fields.Monetary('الفرق', compute='_compute_difference',
        currency_field='currency_id', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    state = fields.Selection([
        ('open', 'مفتوحة'),
        ('closing', 'قيد الإغلاق'),
        ('closed', 'مغلقة'),
        ('verified', 'مدققة'),
    ], 'الحالة', default='open', tracking=True, index=True)
    notes = fields.Text('ملاحظات')
    closing_notes = fields.Text('ملاحظات الإغلاق')

    # Postpaid Billing Fields
    payment_ids = fields.One2many('account.payment', 'cashier_shift_id', string='تحصيلات الفواتير')
    total_collections = fields.Monetary(compute='_compute_totals', string='إجمالي التحصيل', store=True)
    total_cash_collections = fields.Monetary(compute='_compute_totals', string='نقدي التحصيل', store=True)
    total_sales = fields.Monetary('إجمالي المبيعات', compute='_compute_totals', currency_field='currency_id', store=True)
    total_cash = fields.Monetary('إجمالي النقدي', compute='_compute_totals', currency_field='currency_id', store=True)
    total_transactions = fields.Integer('إجمالي المعاملات', compute='_compute_totals', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('جديد'):
                seq = self.env['ir.sequence'].next_by_code('utility.cashier.shift') or '/'
                vals['name'] = _('وردية %s') % seq
        return super().create(vals_list)

    @api.depends('opening_balance', 'total_collections')
    def _compute_expected_balance(self):
        for rec in self:
            rec.expected_balance = (rec.opening_balance or 0.0) + (rec.total_collections or 0.0)

    @api.depends('closing_balance', 'expected_balance')
    def _compute_difference(self):
        for rec in self:
            rec.difference = (rec.closing_balance or 0.0) - (rec.expected_balance or 0.0)

    @api.depends('payment_ids', 'payment_ids.amount', 'payment_ids.state', 'payment_ids.utility_payment_method')
    def _compute_totals(self):
        for rec in self:
            payments = rec.payment_ids.filtered(lambda p: p.state != 'cancel')
            rec.total_collections = sum(payments.mapped('amount'))
            rec.total_cash_collections = sum(payments.filtered(
                lambda p: p.utility_payment_method == 'cash'
            ).mapped('amount'))
            rec.total_sales = rec.total_collections
            rec.total_cash = rec.total_cash_collections
            rec.total_transactions = len(payments)

    @api.constrains('cashier_id', 'state')
    def _check_open_shift_overlap(self):
        for rec in self:
            if rec.state == 'open':
                existing = self.search([
                    ('cashier_id', '=', rec.cashier_id.id),
                    ('state', '=', 'open'),
                    ('id', '!=', rec.id),
                ], limit=1)
                if existing:
                    raise ValidationError(
                        _('الكاشير %s لديه بالفعل وردية مفتوحة (رقم %s). '
                          'يجب إغلاقها أولاً قبل فتح وردية جديدة.')
                        % (rec.cashier_id.name, existing.name))

    def action_close(self):
        for rec in self:
            if rec.state != 'open':
                continue
            rec.write({
                'end_time': fields.Datetime.now(),
                'state': 'closing',
            })

    def action_verify(self):
        for rec in self:
            if rec.state != 'closing':
                continue
            rec.state = 'verified'

    def action_reopen(self):
        for rec in self:
            if rec.state in ('closed', 'verified'):
                raise ValidationError(_('لا يمكن إعادة فتح وردية مدققة أو مغلقة نهائياً.'))
            rec.write({
                'state': 'open',
                'end_time': False,
            })
