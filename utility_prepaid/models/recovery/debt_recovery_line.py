from odoo import api, fields, models


class UtilityPrepaidDebtPolicyLine(models.Model):
    _name = 'utility.prepaid.debt.policy.line'
    _description = 'بند سياسة استقطاع الديون'
    _order = 'priority, id'

    policy_id = fields.Many2one('utility.prepaid.debt.policy', 'السياسة',
        required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', related='policy_id.company_id', store=True)

    debt_type = fields.Selection([
        ('overdue_bill', 'فاتورة متأخرة'),
        ('penalty', 'غرامة'),
        ('service_charge', 'رسوم خدمة'),
        ('other', 'أخرى'),
    ], 'نوع الدين', required=True)

    priority = fields.Integer('الأولوية', default=10,
        help='الأولوية الأقل يتم استقطاعها أولاً')
    recovery_percentage = fields.Float('نسبة الاستقطاع (%)', default=0.0)
    max_amount = fields.Monetary('أقصى مبلغ', currency_field='currency_id')

    description = fields.Char('الوصف')
    currency_id = fields.Many2one('res.currency', related='policy_id.currency_id', store=True)
