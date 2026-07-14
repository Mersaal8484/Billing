from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    utility_sale_order_id = fields.Many2one('sale.order', 'فاتورة آجلة', index=True)
    utility_vending_request_id = fields.Many2one('utility.vending.request', 'طلب بيع مسبق', index=True)
    utility_shift_id = fields.Many2one('utility.cashier.shift', 'الوردية', index=True)
    utility_is_collection = fields.Boolean('تحصيل', default=False)
