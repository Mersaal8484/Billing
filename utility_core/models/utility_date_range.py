from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# ثوابت مشتركة — متزامنة مع utility.region.recurring_rule_type
BILLING_PERIOD_TYPES = [
    ('daily',         'يومي'),
    ('weekly',        'أسبوعي'),
    ('biweekly',      'نصف شهري (15 يوم)'),
    ('monthly',       'شهري'),
    ('quarterly',     'ربع سنوي'),
    ('yearly',        'سنوي'),
]

WORK_TYPE_SELECTION = [
    ('readings', 'قراءات'),
    ('payment',  'دفع'),
    ('other',    'أخرى'),
]


class DateRangeType(models.Model):
    _inherit = 'date.range.type'

    parent_type_id = fields.Many2one(
        'date.range.type',
        string="النوع الرئيسي",
        help="النوع الأب (مثال: السنة المالية هي الأب للأشهر)"
    )
    fiscal_year = fields.Boolean(string="سنة مالية")
    default_billing_period = fields.Selection(
        BILLING_PERIOD_TYPES,
        string="دورة الفوترة الافتراضية",
        help="تُستخدم تلقائياً عند إنشاء فترة من هذا النوع"
    )


class DateRange(models.Model):
    _inherit = 'date.range'

    # ===== الربط الهرمي =====
    parent_id = fields.Many2one(
        'date.range',
        string="الفترة الرئيسية",
        index=True,
        help="مثال: السنة المالية هي الأب للأشهر الاثني عشر"
    )
    child_ids = fields.One2many(
        'date.range', 'parent_id',
        string="الفترات الفرعية"
    )
    previous_range_id = fields.Many2one(
        'date.range',
        string="الفترة السابقة",
        help="الفترة التي تسبق هذه الفترة مباشرة"
    )
    next_range_id = fields.Many2one(
        'date.range',
        string="الفترة التالية",
        compute='_compute_next_range_id',
        store=False
    )

    # ===== المنطقة =====
    region_id = fields.Many2one(
        'utility.region',
        string="المنطقة",
        domain="[('type', '=', 'region')]",
        index=True,
        help="المنطقة الجغرافية المرتبطة بهذه الفترة"
    )
    region_ids = fields.Many2many(
        'utility.region',
        'date_range_region_rel',
        'date_range_id', 'region_id',
        string="المناطق",
        domain="[('type', '=', 'region')]",
        help="يمكن ربط الفترة بأكثر من منطقة"
    )

    # ===== الفوترة والعمل =====
    billing_period = fields.Selection(
        BILLING_PERIOD_TYPES,
        string="تكرار الفوترة",
        default='monthly',
        index=True,
    )
    work_type = fields.Selection(
        WORK_TYPE_SELECTION,
        string="نوع عمل الفترة",
        default='readings',
        index=True,
    )
    is_current_period = fields.Boolean(
        string="الفترة النشطة الحالية",
        default=False,
        index=True,
        tracking=True,
        help="فترة واحدة فقط يمكن أن تكون نشطة لكل نوع فوترة ونوع عمل"
    )

    # ===== حقول إضافية =====
    notes = fields.Text(string="ملاحظات")
    child_count = fields.Integer(
        string="عدد الفترات الفرعية",
        compute='_compute_child_count',
        store=True
    )

    # ===== Compute =====
    @api.depends('child_ids')
    def _compute_child_count(self):
        for rec in self:
            rec.child_count = len(rec.child_ids)

    def _compute_next_range_id(self):
        for rec in self:
            next_range = self.search([
                ('previous_range_id', '=', rec.id)
            ], limit=1)
            rec.next_range_id = next_range.id if next_range else False

    # ===== Constraints =====
    @api.constrains('is_current_period', 'billing_period', 'work_type', 'region_id')
    def _check_single_active_period(self):
        for record in self:
            if not record.is_current_period:
                continue
            domain = [
                ('is_current_period', '=', True),
                ('billing_period',    '=', record.billing_period),
                ('work_type',         '=', record.work_type),
                ('id',                '!=', record.id),
            ]
            if record.region_id:
                domain.append(('region_id', '=', record.region_id.id))

            if self.search_count(domain) > 0:
                raise ValidationError(
                    _("لا يمكن أن يكون هناك أكثر من فترة نشطة واحدة لنفس "
                      "نوع الفوترة ونوع العمل والمنطقة.")
                )

    # ===== Onchange =====
    @api.onchange('billing_period')
    def _onchange_billing_period(self):
        """ربط المنطقة تلقائياً إذا كانت المنطقة الوحيدة تتطابق مع دورة الفوترة"""
        if self.billing_period:
            regions = self.env['utility.region'].search([
                ('type', '=', 'region'),
                ('recurring_rule_type', '=', self.billing_period),
            ])
            if len(regions) == 1:
                self.region_id = regions.id
                self.region_ids = [(6, 0, regions.ids)]
            elif len(regions) > 1:
                self.region_ids = [(6, 0, regions.ids)]

    @api.onchange('type_id')
    def _onchange_type_id(self):
        """استيراد دورة الفوترة الافتراضية من النوع"""
        if self.type_id and self.type_id.default_billing_period:
            self.billing_period = self.type_id.default_billing_period

    # ===== Actions =====
    def action_set_as_current(self):
        """تعيين هذه الفترة كالفترة النشطة الحالية وإلغاء تفعيل الأخريات"""
        self.ensure_one()
        domain = [
            ('is_current_period', '=', True),
            ('billing_period',    '=', self.billing_period),
            ('work_type',         '=', self.work_type),
            ('id',                '!=', self.id),
        ]
        if self.region_id:
            domain.append(('region_id', '=', self.region_id.id))
        self.search(domain).write({'is_current_period': False})
        self.is_current_period = True
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('تم التفعيل'),
                'message': _('تم تعيين "%s" كالفترة النشطة الحالية.') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_children(self):
        """عرض الفترات الفرعية"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('الفترات الفرعية'),
            'res_model': 'date.range',
            'view_mode': 'tree,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {'default_parent_id': self.id, 'default_type_id': self.type_id.id},
        }
