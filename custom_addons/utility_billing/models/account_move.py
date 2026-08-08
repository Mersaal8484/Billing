from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    utility_sale_order_id = fields.Many2one('sale.order', string='فاتورة الكهرباء', index=True)
    service_charge_id = fields.Many2one('utility.service.charge', string='رسم الخدمة', index=True, copy=False, check_company=True)
    meter_number = fields.Char(related='utility_sale_order_id.meter_id.meter_number', string='رقم العداد', store=True)
    current_meter_reading = fields.Float(related='utility_sale_order_id.current_reading', string='القراءة الحالية', store=True)
    consumption_units = fields.Float(related='utility_sale_order_id.consumption', string='وحدات الاستهلاك', store=True)
    consumption_alert = fields.Selection(related='utility_sale_order_id.reading_id.consumption_alert', string='حالة الاستهلاك')

