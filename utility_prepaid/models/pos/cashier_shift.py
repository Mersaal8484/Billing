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

    pos_session_id = fields.Many2one('pos.session', 'جلسة POS', index=True)
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

    vending_request_ids = fields.One2many('utility.vending.request', 'shift_id', 'طلبات البيع')
    postpaid_payment_ids = fields.Many2many(
        'account.payment',
        'utility_shift_account_payment_rel',
        'shift_id', 'payment_id',
        'تحصيلات الدفع الآجل')

    prepaid_total = fields.Monetary('إجمالي الدفع المسبق', compute='_compute_totals',
        currency_field='currency_id', store=True)
    prepaid_cash_total = fields.Monetary('نقدي - دفع مسبق', compute='_compute_totals',
        currency_field='currency_id', store=True)
    prepaid_bank_total = fields.Monetary('بنكي - دفع مسبق', compute='_compute_totals',
        currency_field='currency_id', store=True)
    postpaid_total = fields.Monetary('إجمالي الدفع الآجل', compute='_compute_totals',
        currency_field='currency_id', store=True)
    postpaid_cash_total = fields.Monetary('نقدي - دفع آجل', compute='_compute_totals',
        currency_field='currency_id', store=True)
    postpaid_bank_total = fields.Monetary('بنكي - دفع آجل', compute='_compute_totals',
        currency_field='currency_id', store=True)

    # Compatibility fields for utility_billing
    total_sales = fields.Monetary('إجمالي المبيعات', compute='_compute_totals',
        currency_field='currency_id', store=True,
        help='Compatibility field for utility_billing module')
    total_cash = fields.Monetary('إجمالي النقدي', compute='_compute_totals',
        currency_field='currency_id', store=True,
        help='Compatibility field for utility_billing module')

    vending_count = fields.Integer('عدد عمليات البيع', compute='_compute_counts')
    total_transactions = fields.Integer('إجمالي المعاملات', compute='_compute_counts')

    notes = fields.Text('ملاحظات')
    closing_notes = fields.Text('ملاحظات الإغلاق')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('جديد'):
                seq = self.env['ir.sequence'].next_by_code('utility.cashier.shift') or '/'
                vals['name'] = _('وردية %s') % seq
        return super().create(vals_list)

    @api.depends('opening_balance', 'prepaid_total', 'postpaid_total')
    def _compute_expected_balance(self):
        for rec in self:
            rec.expected_balance = (
                (rec.opening_balance or 0.0)
                + (rec.prepaid_total or 0.0)
                + (rec.postpaid_total or 0.0)
            )

    @api.depends('closing_balance', 'expected_balance')
    def _compute_difference(self):
        for rec in self:
            rec.difference = (rec.closing_balance or 0.0) - (rec.expected_balance or 0.0)

    @api.depends('vending_request_ids', 'vending_request_ids.state',
                 'vending_request_ids.gross_amount', 'postpaid_payment_ids',
                 'postpaid_payment_ids.amount', 'postpaid_payment_ids.payment_type')
    def _compute_totals(self):
        for rec in self:
            completed_vending = rec.vending_request_ids.filtered(
                lambda r: r.state in ('completed', 'token_generated', 'paid'))
            rec.prepaid_total = sum(completed_vending.mapped('gross_amount'))

            pos_vending = rec.vending_request_ids.filtered(
                lambda r: r.pos_order_id and r.state in ('completed', 'token_generated', 'paid'))
            rec.prepaid_cash_total = sum(
                o.amount_total for o in pos_vending.mapped('pos_order_id')
                if all(p.payment_method_id.is_cash_count for p in o.payment_ids))
            rec.prepaid_bank_total = rec.prepaid_total - rec.prepaid_cash_total

            rec.postpaid_total = sum(rec.postpaid_payment_ids.mapped('amount'))
            cash_payments = rec.postpaid_payment_ids.filtered(
                lambda p: p.payment_method_id.is_cash_count)
            rec.postpaid_cash_total = sum(cash_payments.mapped('amount'))
            rec.postpaid_bank_total = rec.postpaid_total - rec.postpaid_cash_total

            # Compatibility fields
            rec.total_sales = rec.prepaid_total + rec.postpaid_total
            rec.total_cash = rec.prepaid_cash_total + rec.postpaid_cash_total

    @api.depends('vending_request_ids', 'postpaid_payment_ids')
    def _compute_counts(self):
        for rec in self:
            rec.vending_count = len(rec.vending_request_ids)
            rec.total_transactions = rec.vending_count + len(rec.postpaid_payment_ids)

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

    def action_view_vending(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('طلبات البيع'),
            'res_model': 'utility.vending.request',
            'domain': [('shift_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
            'context': {'default_shift_id': self.id},
        }
