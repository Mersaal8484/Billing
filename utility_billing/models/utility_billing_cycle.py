from datetime import date, timedelta
from odoo import api, fields, models, _


class DateRange(models.Model):
    _inherit = 'date.range'

    sale_order_ids = fields.One2many('sale.order', 'date_range_id', string='أوامر البيع')
    currency_id = fields.Many2one(
        'res.currency',
        string='العملة',
        default=lambda self: self.env.company.currency_id,
        readonly=True,
    )
    total_bills = fields.Integer('عدد الفواتير', compute='_compute_bill_totals', store=True)
    total_amount = fields.Monetary('الإجمالي', compute='_compute_bill_totals', store=True, currency_field='currency_id')

    @api.depends('sale_order_ids', 'sale_order_ids.amount_total')
    def _compute_bill_totals(self):
        for r in self:
            orders = r.sale_order_ids
            r.total_bills = len(orders)
            r.total_amount = sum(orders.mapped('amount_total'))

    def action_generate_bills(self):
        """Generate bills only from approved periodic readings in this period."""
        self.ensure_one()
        readings = self.env['utility.reading'].search([
            ('date_range_id', '=', self.id),
            ('reading_purpose', '=', 'periodic'),
            ('state', '=', 'approved'),
        ], order='reading_date, id')
        for reading in readings:
            reading.action_generate_bill()
        return True

    @api.model
    def cron_generate_bills_daily(self):
        periods = self.search([('is_current_period', '=', True)])
        for period in periods:
            period.action_generate_bills()
        return True
