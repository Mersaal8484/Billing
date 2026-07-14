from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        result = super()._loader_params_res_partner()
        result['search_params']['fields'].extend([
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
                'fields': [
                    'customer_number', 'partner_id', 'meter_id', 'payment_type',
                    'accounting_balance', 'contract_template_id',
                ],
            }
        }

    def _get_pos_ui_utility_customer(self, params):
        customers = self.env['utility.customer'].search_read(**params['search_params'])
        template_ids = [c['contract_template_id'][0] for c in customers if c.get('contract_template_id')]
        templates = {}
        if template_ids:
            for tpl in self.env['utility.contract.template'].sudo().search_read(
                [('id', 'in', list(set(template_ids)))], ['id', 'price_per_kwh', 'service_charge']
            ):
                templates[tpl['id']] = tpl
        for c in customers:
            tpl_id = c.get('contract_template_id')
            if tpl_id:
                tpl = templates.get(tpl_id[0], {})
                c['price_per_kwh'] = tpl.get('price_per_kwh', 0)
                c['service_charge'] = tpl.get('service_charge', 0)
            else:
                c['price_per_kwh'] = 0
                c['service_charge'] = 0
        return customers

    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        result['search_params']['fields'].extend([
            'is_prepaid_product',
        ])
        return result
