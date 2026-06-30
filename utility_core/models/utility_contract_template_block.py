from odoo import api, fields, models


class UtilityContractTemplateBlock(models.Model):
    _name = 'utility.contract.template.block'
    _description = 'Contract Template Block (Rate Tier)'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'utility.contract.template', 'قالب العقد',
        required=True, index=True, ondelete='cascade')
    sequence = fields.Integer('الترتيب', default=10)
    block_sequence = fields.Integer(related='sequence', store=True, string='رقم الشريحة')
    name = fields.Char('اسم الشريحة')

    from_kwh = fields.Float('من (kWh)', default=0.0)
    to_kwh = fields.Float('إلى (kWh)', default=0.0,
        help='0 = شريحة مفتوحة (لا حد أعلى)')
    price_per_kwh = fields.Float('سعر الكيلوواط/ساعة', required=True)

    from_month = fields.Selection([
        ('1', 'يناير'), ('2', 'فبراير'), ('3', 'مارس'),
        ('4', 'أبريل'), ('5', 'مايو'), ('6', 'يونيو'),
        ('7', 'يوليو'), ('8', 'أغسطس'), ('9', 'سبتمبر'),
        ('10', 'أكتوبر'), ('11', 'نوفمبر'), ('12', 'ديسمبر'),
    ], string='من شهر')
    to_month = fields.Selection([
        ('1', 'يناير'), ('2', 'فبراير'), ('3', 'مارس'),
        ('4', 'أبريل'), ('5', 'مايو'), ('6', 'يونيو'),
        ('7', 'يوليو'), ('8', 'أغسطس'), ('9', 'سبتمبر'),
        ('10', 'أكتوبر'), ('11', 'نوفمبر'), ('12', 'ديسمبر'),
    ], string='إلى شهر')

    time_from = fields.Float('من الساعة', help='0-24')
    time_to = fields.Float('إلى الساعة', help='0-24')
