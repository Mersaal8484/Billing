from odoo import models, fields

class UtilityCustomer(models.Model):
    _inherit = 'utility.customer'

    credit_limit = fields.Monetary('حد الائتمان', default=0.0, currency_field='company_currency_id')
    total_purchases = fields.Monetary(string='إجمالي المشتريات', currency_field='company_currency_id')
    total_kwh_purchased = fields.Float(string='إجمالي الكيلووات المشترى')
    last_purchase_date = fields.Date(string='تاريخ آخر شراء')

    pos_order_count = fields.Integer('طلبات نقاط البيع', compute='_compute_prepaid_smart_buttons')
    vending_request_count = fields.Integer('طلبات الشحن', compute='_compute_prepaid_smart_buttons')
    token_count = fields.Integer('الرموز (Tokens)', compute='_compute_prepaid_smart_buttons')

    def _compute_prepaid_smart_buttons(self):
        for rec in self:
            rec.pos_order_count = self.env['pos.order'].search_count([('utility_account_id', '=', rec.id)])
            rec.vending_request_count = self.env['utility.vending.request'].search_count([('account_id', '=', rec.id)])
            rec.token_count = self.env['utility.token'].search_count([('account_id', '=', rec.id)])

    def action_view_pos_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'طلبات نقاط البيع',
            'res_model': 'pos.order',
            'domain': [('utility_account_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_vending_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'طلبات الشحن',
            'res_model': 'utility.vending.request',
            'domain': [('account_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }


    def action_view_tokens(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'الرموز (Tokens)',
            'res_model': 'utility.token',
            'domain': [('account_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }
