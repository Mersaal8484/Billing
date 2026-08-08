from odoo import models, api

class UtilityDropdownMixin(models.AbstractModel):
    _name = 'utility.dropdown.mixin'
    _description = 'Utility Dropdown Domain Mixin'

    @api.model
    def _get_subscriber_domain(self, category_id=False):
        domain = []
        if category_id:
            domain.append(('category_id', '=', category_id))
        return domain

    @api.model
    def _get_contract_template_domain(self, category_id=False, subscriber_id=False, region_id=False, area_id=False):
        domain = []
        if category_id:
            domain.append(('subscriber_category_ids', 'in', [category_id]))
        if subscriber_id:
            domain.append(('subscriber_ids', 'in', [subscriber_id]))
            
        location_domain = [('scope', '=', 'global')]
        if region_id:
            location_domain = ['|'] + location_domain + [('region_ids', 'in', [region_id])]
        if area_id:
            location_domain = ['|'] + location_domain + [('area_ids', 'in', [area_id])]
            
        return domain + location_domain

    @api.model
    def _get_route_domain(self, region_id=False, area_id=False, zone_id=False):
        domain = []
        if zone_id:
            domain.append(('zone_id', '=', zone_id))
        elif area_id:
            domain.append(('area_id', '=', area_id))
        elif region_id:
            domain.append(('region_id', '=', region_id))
        return domain

    @api.model
    def _get_meter_product_domain(self):
        models = self.env['utility.meter.model'].search([('product_id', '!=', False)])
        product_ids = models.mapped('product_id.id')
        return [('id', 'in', product_ids)]

    @api.model
    def _get_available_new_meter_domain(self):
        return [('customer_id', '=', False), ('active', '=', True)]

    @api.model
    def _get_open_period_domain(self, work_type='readings', billing_period=False, region_id=False):
        period_role = 'reading' if work_type == 'readings' else 'payment'
        # Reading intake must only target active periods. Payment periods follow
        # the same operational rule and only expose live cycles to callers.
        allowed_states = ['open']
        cadence = 'semi_monthly' if billing_period == 'biweekly' else billing_period
        
        domain = [
            ('period_role', '=', period_role),
            ('state', 'in', allowed_states),
        ]
        if cadence:
            domain.append(('billing_cadence', '=', cadence))
        if region_id:
            domain.extend(['|', ('region_ids', '=', False), ('region_ids', 'in', [region_id])])
        return domain
