from odoo import api, fields, models, _


class UtilityPenalty(models.Model):
    _name = 'utility.penalty'
    _description = 'Utility Penalty'
    _order = 'calculated_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    sale_order_id = fields.Many2one('sale.order', 'Sale Order')
    customer_id = fields.Many2one('utility.customer', 'Customer')
    account_id = fields.Many2one('utility.customer', 'Account')
    penalty_type = fields.Selection([
        ('late_payment', 'Late Payment'),
        ('tamper', 'Tampering'),
        ('unauthorized', 'Unauthorized Usage'),
    ], string='Penalty Type', default='late_payment')
    amount = fields.Float('Amount')
    calculated_date = fields.Date('Calculated Date')
    reason = fields.Text('Reason')
    waived = fields.Boolean('Waived', default=False)
    waived_by = fields.Many2one('res.users', 'Waived By')
    state = fields.Selection([
        ('calculated', 'Calculated'),
        ('applied', 'Applied'),
        ('waived', 'Waived'),
    ], string='State', default='calculated')

    @api.model
    def cron_calculate_late_penalties(self):
        overdue_orders = self.env['sale.order'].search([
            ('bill_state', '=', 'overdue'),
            ('balance_due', '>', 0),
        ])
        penalty_percentage = float(self.env['ir.config_parameter'].sudo().get_param('utility.late_penalty_percentage', 1.5))
        for order in overdue_orders:
            already_calculated = self.search([
                ('sale_order_id', '=', order.id),
                ('calculated_date', '=', fields.Date.today()),
                ('penalty_type', '=', 'late_payment')
            ], limit=1)
            if not already_calculated:
                amount = order.balance_due * (penalty_percentage / 100.0)
                if amount > 0:
                    self.create({
                        'sale_order_id': order.id,
                        'customer_id': order.customer_id.id,
                        'account_id': order.customer_id.id,
                        'penalty_type': 'late_payment',
                        'amount': amount,
                        'calculated_date': fields.Date.today(),
                        'reason': f'غرامة تأخير سداد الفاتورة رقم {order.name}',
                        'state': 'calculated',
                    })
                    order.amount_penalty += amount
