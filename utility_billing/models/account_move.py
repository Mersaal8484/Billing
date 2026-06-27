from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    utility_bill_id = fields.Many2one('utility.bill', string='فاتورة الكهرباء', index=True)
    meter_number = fields.Char(related='utility_bill_id.meter_id.meter_number', string='رقم العداد', store=True)
    current_meter_reading = fields.Float(related='utility_bill_id.current_reading', string='القراءة الحالية', store=True)
    consumption_units = fields.Float(related='utility_bill_id.consumption', string='وحدات الاستهلاك', store=True)
    consumption_alert = fields.Selection(related='utility_bill_id.reading_id.consumption_alert', string='حالة الاستهلاك')
