from datetime import date, timedelta
from odoo import api, fields, models, _


class DateRange(models.Model):
    _inherit = 'date.range'

    sale_order_ids = fields.One2many('sale.order', 'date_range_id', string='أوامر البيع')
    total_bills = fields.Integer('عدد الفواتير', compute='_compute_bill_totals', store=True)
    total_amount = fields.Float('الإجمالي', compute='_compute_bill_totals', store=True)

    @api.depends('sale_order_ids', 'sale_order_ids.amount_total')
    def _compute_bill_totals(self):
        for r in self:
            orders = r.sale_order_ids
            r.total_bills = len(orders)
            r.total_amount = sum(orders.mapped('amount_total'))

    def action_generate_bills(self):
        self.ensure_one()
        Reading = self.env['utility.reading']

        accounts = self.env['utility.customer'].search([])

        for account in accounts:
            reading = Reading.search([
                ('account_id', '=', account.id),
                ('state', '=', 'approved'),
                ('date_range_id', '=', self.id),
            ], order='reading_date desc', limit=1)
            if not reading:
                continue
            existing_order = self.env['sale.order'].search([
                ('reading_id', '=', reading.id),
                ('state', '!=', 'cancel'),
            ], limit=1)
            if existing_order:
                continue
            template = account.contract_template_id
            order = self.env['sale.order'].create({
                'partner_id': account.partner_id.id if account.partner_id else self.env.company.partner_id.id,
                'customer_id': account.id,
                'meter_id': reading.meter_id.id,
                'reading_id': reading.id,
                'date_range_id': self.id,
                'date_order': fields.Datetime.now(),
                'period_start': reading.previous_reading_date.date() if reading.previous_reading_date else self.date_start,
                'period_end': reading.reading_date.date() if reading.reading_date else self.date_end,
                'previous_reading': reading.previous_reading,
                'current_reading': reading.reading_value,
                'consumption': reading.consumption,
                'contract_template_id': template.id if template else False,
            })
            order._calculate_amounts()
            reading.state = 'billed'
        return True

    @api.model
    def cron_generate_bills_daily(self):
        periods = self.search([('is_current_period', '=', True)])
        for period in periods:
            period.action_generate_bills()
        return True
