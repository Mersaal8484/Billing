from odoo import api, fields, models, _
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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('skip_tier_validation'):
            templates = records.mapped('template_id')
            templates._validate_contract_template_tiers()
        if not self.env.context.get('_bypass_version_sync'):
            for t in records.mapped('template_id'):
                t._get_or_create_active_version()
        return records

    def write(self, vals):
        templates = self.mapped('template_id')
        res = super().write(vals)
        if not self.env.context.get('skip_tier_validation'):
            all_templates = (templates | self.mapped('template_id'))
            all_templates._validate_contract_template_tiers()
        if not self.env.context.get('_bypass_version_sync'):
            for t in (templates | self.mapped('template_id')):
                t._get_or_create_active_version()
        return res

    def unlink(self):
        templates = self.mapped('template_id')
        res = super().unlink()
        if not self.env.context.get('skip_tier_validation'):
            templates._validate_contract_template_tiers()
        if not self.env.context.get('_bypass_version_sync'):
            for t in templates:
                t._get_or_create_active_version()
        return res

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

    def _get_template_kind_blocks(self):
        self.ensure_one()
        return self.search([
            ('template_id', '=', self.template_id.id),
            ('is_discount', '=', self.is_discount),
        ], order='from_kwh asc, sequence asc, id asc')

    def _get_kind_label(self):
        self.ensure_one()
        return _('شرائح الخصم') if self.is_discount else _('شرائح التسعير')

    @api.constrains('template_id', 'is_discount', 'from_kwh', 'to_kwh', 'sequence')
    def _check_strict_block_order(self):
        """Enforce contiguous tier ranges and sequence order per template/kind."""
        precision = 0.000001
        checked = set()
        for rec in self:
            if not rec.template_id:
                continue
            key = (rec.template_id.id, rec.is_discount)
            if key in checked:
                continue
            checked.add(key)
            blocks = rec._get_template_kind_blocks()
            expected_from = 0.0
            open_block_seen = False
            previous_sequence = False
            for block in blocks:
                label = block._get_kind_label()
                if previous_sequence is not False and block.sequence <= previous_sequence:
                    raise ValidationError(
                        _('%s في قالب العقد "%s" يجب أن تكون مرتبة بتسلسل تصاعدي صارم بدون تكرار.')
                        % (label, block.template_id.name)
                    )
                previous_sequence = block.sequence

                if abs((block.from_kwh or 0.0) - expected_from) > precision:
                    raise ValidationError(
                        _('%s في قالب العقد "%s" غير متصلة. يجب أن تبدأ الشريحة "%s" من %.2f kWh وليس %.2f kWh.')
                        % (label, block.template_id.name, block.name or block.sequence, expected_from, block.from_kwh)
                    )
                if open_block_seen:
                    raise ValidationError(
                        _('%s في قالب العقد "%s" تحتوي شريحة بعد الشريحة المفتوحة. الشريحة المفتوحة يجب أن تكون الأخيرة.')
                        % (label, block.template_id.name)
                    )
                if block.to_kwh == 0:
                    open_block_seen = True
                else:
                    expected_from = block.to_kwh

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

            blocks = self.search([
                ('template_id', '=', rec.template_id.id),
                ('is_discount', '=', rec.is_discount),
            ])
            
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
