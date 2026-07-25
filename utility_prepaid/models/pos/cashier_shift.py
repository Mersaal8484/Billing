import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UtilityCashierShift(models.Model):
    _name = 'utility.cashier.shift'
    _description = 'وردية كاشير الدفع المسبق'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'start_time desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True, index=True,
        default=lambda self: self.env.company,
    )
    name = fields.Char('اسم الوردية', required=True, copy=False, default=lambda self: _('جديد'))
    cashier_id = fields.Many2one(
        'res.users', string='الكاشير', required=True, index=True,
        default=lambda self: self.env.user,
    )
    pos_session_id = fields.Many2one('pos.session', 'جلسة POS', index=True)
    start_time = fields.Datetime('وقت البداية', default=fields.Datetime.now)
    end_time = fields.Datetime('وقت النهاية')
    opening_balance = fields.Monetary('الرصيد الافتتاحي', currency_field='currency_id')
    closing_balance = fields.Monetary('الرصيد الختامي', currency_field='currency_id')
    expected_balance = fields.Monetary(
        'الرصيد المتوقع', compute='_compute_expected_balance',
        currency_field='currency_id', store=True,
    )
    difference = fields.Monetary(
        'الفرق', compute='_compute_difference', currency_field='currency_id', store=True,
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', store=True, readonly=True,
    )
    state = fields.Selection([
        ('open', 'مفتوحة'),
        ('closing', 'قيد الإغلاق'),
        ('verified', 'مدققة'),
    ], string='الحالة', default='open', tracking=True, index=True)
    notes = fields.Text('ملاحظات')
    closing_notes = fields.Text('ملاحظات الإغلاق')

    vending_request_ids = fields.One2many(
        'utility.vending.request', 'shift_id', string='طلبات البيع',
    )
    prepaid_total = fields.Monetary(
        'إجمالي الدفع المسبق', compute='_compute_totals',
        currency_field='currency_id', store=True,
    )
    prepaid_cash_total = fields.Monetary(
        'نقدي - دفع مسبق', compute='_compute_totals',
        currency_field='currency_id', store=True,
    )
    prepaid_bank_total = fields.Monetary(
        'بنكي - دفع مسبق', compute='_compute_totals',
        currency_field='currency_id', store=True,
    )
    total_sales = fields.Monetary(
        'إجمالي المبيعات', compute='_compute_totals',
        currency_field='currency_id', store=True,
    )
    total_cash = fields.Monetary(
        'إجمالي النقدي', compute='_compute_totals',
        currency_field='currency_id', store=True,
    )
    total_transactions = fields.Integer('إجمالي المعاملات', compute='_compute_totals', store=True)
    vending_count = fields.Integer('عدد عمليات البيع', compute='_compute_counts')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('جديد'):
                sequence = self.env['ir.sequence'].next_by_code('utility.cashier.shift') or '/'
                vals['name'] = _('وردية %s') % sequence
        return super().create(vals_list)

    @api.depends(
        'vending_request_ids.state', 'vending_request_ids.gross_amount',
        'vending_request_ids.pos_order_id.payment_ids.amount',
        'vending_request_ids.pos_order_id.payment_ids.payment_method_id.is_cash_count',
    )
    def _compute_totals(self):
        for shift in self:
            completed = shift.vending_request_ids.filtered(
                lambda request: request.state in ('completed', 'token_generated', 'paid')
            )
            shift.prepaid_total = sum(completed.mapped('gross_amount'))
            payments = completed.mapped('pos_order_id.payment_ids')
            cash_total = sum(
                payments.filtered('payment_method_id.is_cash_count').mapped('amount')
            )
            shift.prepaid_cash_total = cash_total
            shift.prepaid_bank_total = shift.prepaid_total - cash_total
            shift.total_sales = shift.prepaid_total
            shift.total_cash = cash_total
            shift.total_transactions = len(completed)

    @api.depends('opening_balance', 'prepaid_cash_total')
    def _compute_expected_balance(self):
        for shift in self:
            shift.expected_balance = (
                (shift.opening_balance or 0.0) + (shift.prepaid_cash_total or 0.0)
            )

    @api.depends('closing_balance', 'expected_balance')
    def _compute_difference(self):
        for shift in self:
            shift.difference = (
                (shift.closing_balance or 0.0) - (shift.expected_balance or 0.0)
            )

    @api.depends('vending_request_ids')
    def _compute_counts(self):
        for shift in self:
            shift.vending_count = len(shift.vending_request_ids)

    @api.constrains('cashier_id', 'company_id', 'state')
    def _check_open_shift_overlap(self):
        open_shifts = self.filtered(lambda record: record.state == 'open')
        if not open_shifts:
            return
        candidates = self.search([
            ('cashier_id', 'in', open_shifts.mapped('cashier_id').ids),
            ('company_id', 'in', open_shifts.mapped('company_id').ids),
            ('state', '=', 'open'),
        ])
        grouped = {}
        for candidate in candidates:
            key = (candidate.cashier_id.id, candidate.company_id.id)
            grouped.setdefault(key, self.env['utility.cashier.shift'])
            grouped[key] |= candidate
        duplicate = next((records for records in grouped.values() if len(records) > 1), False)
        if duplicate:
            raise ValidationError(
                _('الكاشير %s لديه أكثر من وردية دفع مسبق مفتوحة: %s.')
                % (duplicate[0].cashier_id.name, ', '.join(duplicate.mapped('name')))
            )

    def action_close(self):
        self.filtered(lambda shift: shift.state == 'open').write({
            'end_time': fields.Datetime.now(),
            'state': 'closing',
        })

    def action_verify(self):
        self.filtered(lambda shift: shift.state == 'closing').write({'state': 'verified'})

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