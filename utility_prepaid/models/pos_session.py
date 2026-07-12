from odoo import models

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        result = super()._loader_params_res_partner()
        result['search_params']['fields'].extend([
            'utility_prepaid_balance',
            'utility_postpaid_balance'
        ])
        return result

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        result.append('utility.customer')
        return result

    def _loader_params_utility_customer(self):
        return {
            'search_params': {
                'domain': [('state', '=', 'active')],
                'fields': ['customer_number', 'partner_id', 'meter_id', 'payment_type', 'prepaid_balance', 'accounting_balance'],
            }
        }

    def _get_pos_ui_utility_customer(self, params):
        return self.env['utility.customer'].search_read(**params['search_params'])
