from odoo import api, fields, models, _
from datetime import date


class UtilitySaleOrderCron(models.Model):
    _inherit = 'sale.order'

    @api.model
    def cron_create_disconnection_orders(self):
        params = self.env['ir.config_parameter'].sudo()
        days = int(params.get_param('utility.auto_disconnection_days', 90))
        batch_size = int(params.get_param('utility.disconnection_batch_size', 200))
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=days)
        orders = self.search([
            ('customer_id', '!=', False),
            ('bill_state', '=', 'overdue'),
            ('balance_due', '>', 0),
            ('date_order', '<=', cutoff),
            ('disconnection_order_id', '=', False),
        ], limit=batch_size, order='date_order asc, id asc')
        created = self.env['utility.service.order']
        for order in orders:
            existing = order._find_open_service_order('disconnection')
            if existing:
                order.disconnection_order_id = existing.id
                continue
            service_order = self.env['utility.service.order'].create({
                'service_type': 'disconnection',
                'priority': 'high',
                'customer_id': order.customer_id.id,
                'meter_id': order.meter_id.id,
                'description': _('فصل خدمة آلي بسبب متأخرات الفاتورة %s بمبلغ %.2f بعد %s يوم.')
                               % (order.name, order.balance_due, days),
            })
            order.disconnection_order_id = service_order.id
            created |= service_order
        return len(created)

    @api.model
    def cron_update_overdue_orders(self):
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'utility.billing_batch_size', 1000))
        self.search([
            ('bill_state', 'not in', ('paid', 'cancelled', 'overdue')),
            ('date_order', '<', date.today()),
            ('balance_due', '>', 0),
        ], limit=batch_size)._compute_bill_state()

    @api.model
    def cron_send_due_reminders(self):
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'utility.reminder_batch_size', 500))
        orders = self.search([
            ('bill_state', '=', 'overdue'),
            ('balance_due', '>', 0),
            ('customer_id', '!=', False),
        ], limit=batch_size, order='date_order asc, id asc')
        orders._create_overdue_notifications()
        return len(orders)

    @api.model
    def cron_generate_bills_daily(self):
        Reading = self.env.get('utility.reading')
        if not Reading:
            return 0
        return Reading._cron_generate_bills()
