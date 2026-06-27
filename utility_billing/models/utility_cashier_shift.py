from odoo import api, fields, models, _


class UtilityCashierShift(models.Model):
    _inherit = 'utility.cashier.shift'

    payment_ids = fields.One2many('account.payment', 'cashier_shift_id', string='تحصيلات الفواتير')
    total_collections = fields.Monetary(compute='_compute_collection_totals', string='إجمالي التحصيل', store=True)
    total_cash_collections = fields.Monetary(compute='_compute_collection_totals', string='نقدي التحصيل', store=True)

    @api.depends('payment_ids', 'state')
    def _compute_collection_totals(self):
        for rec in self:
            payments = rec.payment_ids.filtered(lambda p: p.state != 'cancelled')
            rec.total_collections = sum(payments.mapped('amount'))
            rec.total_cash_collections = sum(payments.filtered(
                lambda p: p.utility_payment_method == 'cash'
            ).mapped('amount'))

    @api.depends('opening_balance', 'total_sales', 'total_collections')
    def _compute_expected_balance(self):
        for rec in self:
            rec.expected_balance = (rec.opening_balance or 0.0) + \
                (rec.total_sales or 0.0) + (rec.total_collections or 0.0)
