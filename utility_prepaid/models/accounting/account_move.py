from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    utility_vending_request_id = fields.Many2one('utility.vending.request', 'طلب بيع مسبق',
        index=True)
    utility_reversal_id = fields.Many2one('utility.vending.reversal', 'طلب عكس', index=True)
    utility_adjustment_id = fields.Many2one('utility.prepaid.adjustment', 'تسوية', index=True)
    utility_is_prepaid_entry = fields.Boolean('قيد دفع مسبق', default=False, index=True)

    def action_view_vending_request(self):
        self.ensure_one()
        if self.utility_vending_request_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'طلب بيع مسبق',
                'res_model': 'utility.vending.request',
                'res_id': self.utility_vending_request_id.id,
                'view_mode': 'form',
            }
