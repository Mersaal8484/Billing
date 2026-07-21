import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UtilityCashierShift(models.Model):
    _inherit = 'utility.cashier.shift'

    pos_session_id = fields.Many2one('pos.session', 'جلسة POS', index=True)
    vending_request_ids = fields.One2many('utility.vending.request', 'shift_id', 'طلبات البيع')
    prepaid_total = fields.Monetary('إجمالي الدفع المسبق', compute='_compute_totals',
        currency_field='currency_id', store=True)
    prepaid_cash_total = fields.Monetary('نقدي - دفع مسبق', compute='_compute_totals',
        currency_field='currency_id', store=True)
    prepaid_bank_total = fields.Monetary('بنكي - دفع مسبق', compute='_compute_totals',
        currency_field='currency_id', store=True)

    postpaid_payment_ids = fields.Many2many(
        'account.payment',
        'utility_shift_account_payment_rel',
        'shift_id', 'payment_id',
        'تحصيلات الدفع الآجل')
    postpaid_total = fields.Monetary('إجمالي الدفع الآجل (كود قديم)', compute='_compute_totals',
        currency_field='currency_id', store=True)
    postpaid_cash_total = fields.Monetary('نقدي - دفع آجل (كود قديم)', compute='_compute_totals',
        currency_field='currency_id', store=True)
    postpaid_bank_total = fields.Monetary('بنكي - دفع آجل (كود قديم)', compute='_compute_totals',
        currency_field='currency_id', store=True)

    vending_count = fields.Integer('عدد عمليات البيع', compute='_compute_counts')

    @api.depends('vending_request_ids', 'vending_request_ids.state',
                 'vending_request_ids.gross_amount', 'postpaid_payment_ids',
                 'postpaid_payment_ids.amount', 'postpaid_payment_ids.payment_type',
                 'payment_ids', 'payment_ids.amount', 'payment_ids.state')
    def _compute_totals(self):
        super()._compute_totals()
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

            # postpaid_payment_ids calculations
            rec.postpaid_total = sum(rec.postpaid_payment_ids.mapped('amount'))
            cash_payments = rec.postpaid_payment_ids.filtered(
                lambda p: p.payment_method_id.is_cash_count)
            rec.postpaid_cash_total = sum(cash_payments.mapped('amount'))
            rec.postpaid_bank_total = rec.postpaid_total - rec.postpaid_cash_total

            # Update combined compatibility fields
            rec.total_sales = rec.prepaid_total + rec.total_collections
            rec.total_cash = rec.prepaid_cash_total + rec.total_cash_collections
            rec.total_transactions = len(completed_vending) + len(rec.payment_ids)

    @api.depends('vending_request_ids')
    def _compute_counts(self):
        for rec in self:
            rec.vending_count = len(rec.vending_request_ids)

    @api.depends('opening_balance', 'prepaid_total', 'total_collections')
    def _compute_expected_balance(self):
        for rec in self:
            rec.expected_balance = (
                (rec.opening_balance or 0.0)
                + (rec.prepaid_total or 0.0)
                + (rec.total_collections or 0.0)
            )

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
