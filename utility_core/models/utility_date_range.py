from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

RECURRING_RULE_TYPES = [
    ('monthly', 'شهري'),
    ('bi_monthly', 'نصف شهري'),
    ('quarterly', 'ربع سنوي'),
    ('yearly', 'سنوي'),
]

WORK_TYPE_SELECTION = [
    ('readings', 'قراءات'),
    ('payment', 'دفع'),
    ('other', 'أخرى'),
]


class DateRangeType(models.Model):
    _inherit = 'date.range.type'

    parent_type_id = fields.Many2one('date.range.type', string="النوع الرئيسي")
    fiscal_year = fields.Boolean(string="سنة مالية")


class DateRange(models.Model):
    _inherit = 'date.range'

    parent_id = fields.Many2one('date.range', string="الفترة الرئيسية")
    previous_range_id = fields.Many2one('date.range', string="الفترة السابقة")
    region_id = fields.Many2one(
        'utility.region', string="المنطقة",
        domain="[('type', '=', 'region')]")
    billing_period = fields.Selection(
        RECURRING_RULE_TYPES, string="تكرار الفوترة", default='monthly')
    work_type = fields.Selection(
        WORK_TYPE_SELECTION, string="نوع عمل الفترة", default='readings')
    is_current_period = fields.Boolean(string="الفترة الحالية النشطة", default=False)

    @api.constrains('is_current_period', 'billing_period', 'work_type')
    def _check_single_active_period(self):
        for record in self:
            if record.is_current_period:
                domain = [
                    ('is_current_period', '=', True),
                    ('billing_period', '=', record.billing_period),
                    ('work_type', '=', record.work_type),
                    ('id', '!=', record.id),
                ]
                if self.search_count(domain) > 0:
                    raise ValidationError(
                        _("لا يمكن أن يكون هناك أكثر من فترة نشطة واحدة لنفس نوع الفوترة ونوع العمل."))

    @api.onchange('billing_period')
    def _onchange_billing_period(self):
        if self.billing_period:
            regions = self.env['utility.region'].search([
                ('type', '=', 'region'),
                ('recurring_rule_type', '=', self.billing_period),
            ])
            if len(regions) == 1:
                self.region_id = regions.id
