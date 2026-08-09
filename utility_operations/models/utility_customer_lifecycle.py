from odoo import fields, models


class UtilityCustomerMeterAssignmentOperations(models.Model):
    _inherit = 'utility.customer.meter.assignment'

    service_order_id = fields.Many2one(
        'utility.service.order', string='أمر الخدمة', ondelete='restrict')


class UtilityCustomerLifecycleEventOperations(models.Model):
    _inherit = 'utility.customer.lifecycle.event'

    service_order_id = fields.Many2one('utility.service.order', string='أمر الخدمة')


class UtilityCustomerLifecycleWizardOperations(models.TransientModel):
    _inherit = 'utility.customer.lifecycle.wizard'

    service_order_id = fields.Many2one(
        'utility.service.order', string='أمر الخدمة',
        domain="[('customer_id', '=', customer_id), ('state', '=', 'completed')]")
