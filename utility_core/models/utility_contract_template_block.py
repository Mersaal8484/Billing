from odoo import api, fields, models
from odoo.exceptions import ValidationError


class UtilityContractTemplateBlock(models.Model):
    _name = 'utility.contract.template.block'
    _description = 'شريحة قالب العقد'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'utility.contract.template', 'قالب العقد',
        required=True, index=True, ondelete='cascade')
    currency_id = fields.Many2one(
        'res.currency',
        related='template_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )
    sequence = fields.Integer('الترتيب', default=10)
    block_sequence = fields.Integer(related='sequence', store=True, string='رقم الشريحة')
    name = fields.Char('اسم الشريحة')
    is_discount = fields.Boolean('شريحة خصم', default=False)

    from_kwh = fields.Float('من (kWh)', default=0.0)
    to_kwh = fields.Float('إلى (kWh)', default=0.0,
        help='0 = شريحة مفتوحة (لا حد أعلى)')
    price_per_kwh = fields.Monetary('سعر الكيلوواط/ساعة', required=True, currency_field='currency_id')

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

    # ── FIX: قيود منطقية على نطاق الشرائح ───────────────────────────────────────
    @api.constrains('from_kwh', 'to_kwh')
    def _check_kwh_range(self):
        for rec in self:
            # from يجب أن يكون أكبر من أو يساوي 0
            if rec.from_kwh < 0:
                raise ValidationError(
                    'قيمة “من (kWh)” لا يمكن أن تكون سالبة في الشريحة [%s].' % (rec.name or rec.sequence)
                )
            # to_kwh = 0 يعني شريحة مفتوحة (لا حد أعلى) — مسموح
            if rec.to_kwh > 0 and rec.to_kwh <= rec.from_kwh:
                raise ValidationError(
                    'قيمة “إلى (kWh)” يجب أن تكون أكبر من “من (kWh)” '
                    'في الشريحة [%s]. (%.2f ≤ %.2f)'
                    % (rec.name or rec.sequence, rec.to_kwh, rec.from_kwh)
                )

    @api.constrains('price_per_kwh')
    def _check_positive_price(self):
        for rec in self:
            if rec.price_per_kwh < 0:
                raise ValidationError(
                    'سعر الكيلووات/ساعة لا يمكن أن يكون سالباً '
                    'في الشريحة [%s].' % (rec.name or rec.sequence)
                )

    @api.constrains('from_kwh', 'to_kwh', 'template_id', 'is_discount')
    def _check_no_overlapping_blocks(self):
        """منع تداخل نطاقات الشرائح داخل نفس القالب."""
        for rec in self:
            if not rec.template_id:
                continue

            blocks = rec.template_id.block_ids.filtered(lambda b: b.is_discount == rec.is_discount)
            
            if rec.to_kwh == 0:
                open_blocks = blocks.filtered(lambda b: b.to_kwh == 0 and b.id != rec.id)
                if open_blocks:
                    raise ValidationError(
                        'يوجد بالفعل شريحة مفتوحة بدون حد أعلى في القالب لهذا النوع. '
                        'لا يمكن وجود أكثر من شريحة مفتوحة واحدة.'
                    )
                overlapping = blocks.filtered(lambda b: b.to_kwh > 0 and b.id != rec.id and b.to_kwh > rec.from_kwh)
                if overlapping:
                    raise ValidationError(
                        'الشريحة المفتوحة تتداخل مع شريحة مغلقة أخرى في القالب. '
                        'تأكد من أن بداية الشريحة المفتوحة أكبر من أو تساوي نهاية جميع الشرائح المغلقة.'
                    )
                continue

            for other in blocks:
                if other.id == rec.id:
                    continue
                if other.to_kwh == 0:
                    if other.from_kwh < rec.to_kwh:
                        raise ValidationError(
                            'الشريحة [%s: %.0f – %.0f] تتداخل مع شريحة مفتوحة في القالب. '
                            % (rec.name or rec.sequence, rec.from_kwh, rec.to_kwh)
                        )
                else:
                    if rec.from_kwh < other.to_kwh and other.from_kwh < rec.to_kwh:
                        raise ValidationError(
                            'الشريحة [%s: %.0f – %.0f] تتداخل مع شريحة أخرى في القالب. '
                            'تأكد من عدم تداخل نطاقات kWh.'
                            % (rec.name or rec.sequence, rec.from_kwh, rec.to_kwh)
                        )
