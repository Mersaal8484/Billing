from odoo import api, fields, models, _


class UtilityPenalty(models.Model):
    _name = 'utility.penalty'
    _description = 'Utility Penalty'
    _order = 'calculated_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    bill_id = fields.Many2one('utility.bill', 'Bill')
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
        # البحث عن الفواتير المتأخرة المستحقة للغرامة
        overdue_bills = self.env['utility.bill'].search([
            ('state', '=', 'overdue'),
            ('balance_due', '>', 0),
        ])
        penalty_percentage = float(self.env['ir.config_parameter'].sudo().get_param('utility.late_penalty_percentage', 1.5))
        for bill in overdue_bills:
            # التحقق مما إذا كانت الغرامة قد تم احتسابها اليوم بالفعل لتجنب التكرار
            already_calculated = self.search([
                ('bill_id', '=', bill.id),
                ('calculated_date', '=', fields.Date.today()),
                ('penalty_type', '=', 'late_payment')
            ], limit=1)
            if not already_calculated:
                amount = bill.balance_due * (penalty_percentage / 100.0)
                if amount > 0:
                    self.create({
                        'bill_id': bill.id,
                        'customer_id': bill.customer_id.id,
                        'account_id': bill.account_id.id,
                        'penalty_type': 'late_payment',
                        'amount': amount,
                        'calculated_date': fields.Date.today(),
                        'reason': f'غرامة تأخير سداد الفاتورة رقم {bill.bill_number}',
                        'state': 'calculated',
                    })
                    # إضافة الغرامة إلى مبلغ الفاتورة الإجمالي وإعادة حساب المبالغ
                    bill.amount_penalty += amount
                    bill.amount_total += amount

