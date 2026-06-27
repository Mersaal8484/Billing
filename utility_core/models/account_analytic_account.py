from odoo import api, fields, models, _


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    utility_account_id = fields.Many2one('utility.customer', string='حساب الكهرباء', index=True)
    utility_customer_id = fields.Many2one('utility.customer', related='utility_account_id', store=True)
    
    meter_id = fields.Char(related='utility_account_id.meter_id.meter_number', string='رقم العداد', store=True)
    meter_type = fields.Char(related='utility_account_id.meter_id.meter_type_id.name', string='نوع العداد', readonly=True)
    meter_vastype = fields.Selection(related='utility_account_id.meter_id.phase', string='فاز العداد', readonly=True)
    
    meter_current_reading = fields.Float(compute='_compute_meter_readings', string='القراءة الحالية')
    meter_last_invo_reading = fields.Float(compute='_compute_meter_readings', string='آخر قراءة مفوترة')
    
    region_id = fields.Many2one(related='utility_account_id.region_id', store=True)
    area_id = fields.Many2one(related='utility_account_id.area_id', store=True)
    transformer_id = fields.Many2one(related='utility_account_id.meter_id.transformer_id', string='المحول')
    contract_state = fields.Selection(related='utility_account_id.contract_state', string='حالة الاشتراك')
    
    invoice_count = fields.Integer(compute='_compute_smart_buttons')
    reading_count = fields.Integer(compute='_compute_smart_buttons')
    payment_count = fields.Integer(compute='_compute_smart_buttons')

    def _compute_meter_readings(self):
        Reading = self.env.get('utility.reading')
        SaleOrder = self.env.get('sale.order')
        for rec in self:
            account = rec.utility_account_id
            if account and Reading:
                last = Reading.search([
                    ('account_id', '=', account.id),
                    ('state', 'in', ['approved', 'billed']),
                ], order='reading_date desc', limit=1)
                rec.meter_current_reading = last.reading_value if last else 0.0
            else:
                rec.meter_current_reading = 0.0
            if account and SaleOrder:
                last_order = SaleOrder.search([
                    ('customer_id', '=', account.id),
                    ('bill_state', 'in', ['confirmed', 'paid']),
                ], order='period_end desc', limit=1)
                rec.meter_last_invo_reading = last_order.current_reading if last_order else 0.0
            else:
                rec.meter_last_invo_reading = 0.0

    def _compute_smart_buttons(self):
        Bill = self.env.get('sale.order')
        Reading = self.env.get('utility.reading')
        for rec in self:
            account = rec.utility_account_id
            rec.invoice_count = Bill.search_count([('customer_id', '=', account.id)]) if account and Bill else 0
            rec.reading_count = Reading.search_count([('account_id', '=', account.id)]) if account and Reading else 0
            rec.payment_count = 0
