from odoo import api, fields, models


class UtilityVendingChargeLine(models.Model):
    _name = 'utility.vending.charge.line'
    _description = 'بند احتساب الشحنة'
    _order = 'sequence, id'

    vending_request_id = fields.Many2one('utility.vending.request', 'طلب البيع',
        required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', related='vending_request_id.company_id', store=True)

    charge_type = fields.Selection([
        ('energy', 'قيمة الطاقة'),
        ('service', 'رسوم الخدمة'),
        ('tax', 'الضرائب'),
        ('maintenance', 'رسوم الصيانة'),
        ('debt_recovery', 'استقطاع الديون'),
        ('penalty', 'الغرامات'),
        ('agent_commission', 'عمولة الوكيل'),
        ('rounding', 'التقريب'),
        ('other', 'رسوم أخرى'),
    ], 'نوع البند', required=True, index=True)

    description = fields.Char('الوصف')
    amount = fields.Monetary('المبلغ', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', related='vending_request_id.currency_id', store=True)
    sequence = fields.Integer('التسلسل', default=10)
