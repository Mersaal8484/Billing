from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

# ثوابت مشتركة
BILLING_PERIOD_TYPES = [
    ('daily',         'يومي'),
    ('weekly',        'أسبوعي'),
    ('semi_monthly',  'نصف شهري'),
    ('monthly',       'شهري'),
    ('quarterly',     'ربع سنوي'),
    ('yearly',        'سنوي'),
    ('biweekly',      'نصف شهري (مستبدل - 15 يوم)'),
]

WORK_TYPE_SELECTION = [
    ('readings', 'قراءات'),
    ('payment',  'دفع'),
    ('other',    'أخرى'),
]

PERIOD_ROLE_SELECTION = [
    ('reading', 'دورة قراءة وفوترة'),
    ('payment', 'دورة سداد وتحصيل'),
]

READING_STATE_SELECTION = [
    ('planned',        'مخطط'),
    ('reading_open',   'نافذة القراءة مفتوحة'),
    ('reading_closed', 'نافذة القراءة مغلقة'),
    ('reviewing',      'قيد المراجعة'),
    ('review_closed',  'اكتملت المراجعة'),
    ('billing',        'قيد الفوترة'),
    ('accounting',     'قيد التظهير المحاسبي'),
    ('closing',        'قيد المطابقة والإغلاق'),
    ('closed',         'مغلقة'),
    ('locked',         'مقفلة تاريخياً'),
    ('reopened',       'معاد فتحها استثنائياً'),
]

PAYMENT_STATE_SELECTION = [
    ('planned',    'مخطط'),
    ('open',       'نافذة التحصيل مفتوحة'),
    ('closing',    'قيد الإغلاق'),
    ('closed',     'مغلقة'),
    ('reconciled', 'تمت المطابقة'),
    ('locked',     'مقفلة تاريخياً'),
    ('reopened',   'معاد فتحها استثنائياً'),
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

    # ===== التعريف الأساسي والرمز =====
    period_code = fields.Char(
        string="رمز الفترة الفريد",
        required=True,
        copy=False,
        index=True,
        help="رمز معرف فريد للنظام والربط (مثال: SEMI-2026-08-H1 أو PAY-SEMI-2026-08-H1)"
    )
    period_role = fields.Selection(
        PERIOD_ROLE_SELECTION,
        string="دور الفترة",
        default='reading',
        required=True,
        index=True,
    )
    billing_cadence = fields.Selection(
        BILLING_PERIOD_TYPES,
        string="دورية الفوترة المستهدفة",
        default='monthly',
        required=True,
        index=True,
    )

    # ===== حالات دورة الحياة المستقلة =====
    state = fields.Selection(
        READING_STATE_SELECTION,
        string="حالة الفترة",
        default='planned',
        required=True,
        index=True,
        copy=False,
        tracking=True,
    )

    # ===== نطاق المناطق المعنية =====
    region_ids = fields.Many2many(
        'utility.region',
        'utility_date_range_region_rel',
        'period_id',
        'region_id',
        string="المناطق المشتركة في الفترة",
        domain="[('type', '=', 'region')]",
        help="المناطق التي تنطبق عليها هذه الفترة الزمنية"
    )

    # ===== التواريخ والنوافذ الزمنية التفصيلية =====
    consumption_start = fields.Date(
        string="بداية فترة الاستهلاك",
        help="تاريخ بداية دورة الاستهلاك الفعلية للمشتركين"
    )
    consumption_end = fields.Date(
        string="نهاية فترة الاستهلاك",
        help="تاريخ نهاية دورة الاستهلاك الفعلية للمشتركين"
    )
    reading_window_start = fields.Datetime(
        string="بداية نافذة القراءة والرفع",
        help="الوقت الذي يُسمح فيه للقراء برفع وتوثيق القراءات"
    )
    reading_window_end = fields.Datetime(
        string="نهاية نافذة القراءة والرفع",
        help="الوقت الموعد النهائي المسموح فيه بالرفع المباشر"
    )
    payment_window_start = fields.Datetime(
        string="بداية نافذة التحصيل",
        help="بداية تاريخ التحصيل المسموح لهذه الدورة"
    )
    payment_window_end = fields.Datetime(
        string="نهاية نافذة التحصيل",
        help="نهاية تاريخ التحصيل المسموح لهذه الدورة"
    )

    # ===== الربط الوثيق بين فترة السداد وفترة القراءة =====
    reading_period_id = fields.Many2one(
        'date.range',
        string="فترة القراءة والمرجع الأساسي",
        domain="[('period_role', '=', 'reading')]",
        index=True,
        ondelete='restrict',
        help="فترة القراءة والاستهلاك التي تولدت عنها فواتير هذا التحصيل"
    )
    payment_period_ids = fields.One2many(
        'date.range',
        'reading_period_id',
        string="فترات السداد المرتبطة"
    )

    # ===== الربط الهرمي والسلسلة =====
    parent_id = fields.Many2one(
        'date.range',
        string="الفترة الأب (مثل السنة المالية)",
        index=True,
        help="للهيكلة التقويمية العامة (مثال: السنة المالية للأشهر)"
    )
    child_ids = fields.One2many(
        'date.range', 'parent_id',
        string="الفترات الفرعية"
    )
    previous_period_id = fields.Many2one(
        'date.range',
        string="الفترة السابقة",
        index=True,
        help="الفترة التاريخية السابقة مباشرة لنفس الدورية والنطاق"
    )
    next_period_id = fields.Many2one(
        'date.range',
        string="الفترة التالية",
        compute='_compute_next_period_id',
        store=False
    )

    # ===== التوافق مع الحقول القديمة =====
    billing_period = fields.Selection(
        BILLING_PERIOD_TYPES,
        string="تكرار الفوترة (قديم)",
        compute='_compute_legacy_billing_period',
        inverse='_inverse_legacy_billing_period',
        store=True,
        index=True,
    )
    work_type = fields.Selection(
        WORK_TYPE_SELECTION,
        string="نوع عمل الفترة (قديم)",
        compute='_compute_legacy_work_type',
        inverse='_inverse_legacy_work_type',
        store=True,
        index=True,
    )
    is_current_period = fields.Boolean(
        string="الفترة النشطة الحالية",
        compute='_compute_is_current_period',
        store=True,
        index=True,
        help="مؤشر توافقي يعبر عن كون الفترة في حالة عمل مفتوحة"
    )

    # ===== تتبع Workflow والتوقيتات =====
    workflow_id = fields.Char(string="معرف workflow Temporal", copy=False)
    workflow_run_id = fields.Char(string="معرف Run Temporal", copy=False)
    opened_at = fields.Datetime(string="تاريخ الفتح", readonly=True)
    closed_at = fields.Datetime(string="تاريخ الإغلاق", readonly=True)
    locked_at = fields.Datetime(string="تاريخ الإقفال", readonly=True)

    # ===== المؤشرات المجمعة (Metrics & Aggregations) =====
    expected_accounts = fields.Integer(string="الحسابات المتوقعة", compute='_compute_period_statistics')
    received_readings = fields.Integer(string="القراءات المستلمة", compute='_compute_period_statistics')
    missing_readings = fields.Integer(string="القراءات المفقودة", compute='_compute_period_statistics')
    images_ready = fields.Integer(string="الصور الجاهزة", compute='_compute_period_statistics')
    pending_review = fields.Integer(string="قراءات بانتظار المراجعة", compute='_compute_period_statistics')
    approved_readings = fields.Integer(string="القراءات المعتمدة", compute='_compute_period_statistics')
    rejected_readings = fields.Integer(string="القراءات المرفوضة", compute='_compute_period_statistics')
    bills_generated = fields.Integer(string="الفواتير المنشأة", compute='_compute_period_statistics')
    billed_amount = fields.Monetary(string="إجمالي الفواتير", compute='_compute_period_statistics', currency_field='currency_id')
    accounting_total = fields.Monetary(string="إجمالي الفواتير المحاسبية", compute='_compute_period_statistics', currency_field='currency_id')
    collected_in_window = fields.Monetary(string="التحصيل في النافذة", compute='_compute_period_statistics', currency_field='currency_id')
    outstanding_amount = fields.Monetary(string="المبلغ المتأخر", compute='_compute_period_statistics', currency_field='currency_id')
    collection_rate = fields.Float(string="نسبة التحصيل %", compute='_compute_period_statistics')
    exception_count = fields.Integer(string="عدد الاستثناءات المعلقة", compute='_compute_period_statistics')

    currency_id = fields.Many2one('res.currency', string='العملة', default=lambda self: self.env.company.currency_id)
    notes = fields.Text(string="ملاحظات")
    log_ids = fields.One2many('date.range.log', 'period_id', string="سجل التدقيق والمتابعة", readonly=True)
    child_count = fields.Integer(string="عدد الفترات الفرعية", compute='_compute_child_count', store=True)

    _sql_constraints = [
        ('period_code_unique', 'UNIQUE(period_code)', 'رمز الفترة يجب أن يكون فريداً على مستوى النظام!'),
    ]

    # ===== Compute & Sync Logic =====
    @api.depends('billing_cadence')
    def _compute_legacy_billing_period(self):
        for rec in self:
            rec.billing_period = rec.billing_cadence

    def _inverse_legacy_billing_period(self):
        for rec in self:
            if rec.billing_period:
                cadence = 'semi_monthly' if rec.billing_period == 'biweekly' else rec.billing_period
                rec.billing_cadence = cadence

    @api.depends('period_role')
    def _compute_legacy_work_type(self):
        for rec in self:
            rec.work_type = 'readings' if rec.period_role == 'reading' else 'payment'

    def _inverse_legacy_work_type(self):
        for rec in self:
            if rec.work_type == 'payment':
                rec.period_role = 'payment'
            elif rec.work_type == 'readings':
                rec.period_role = 'reading'

    @api.depends('state')
    def _compute_is_current_period(self):
        for rec in self:
            rec.is_current_period = rec.state in ('reading_open', 'open')

    @api.depends('child_ids')
    def _compute_child_count(self):
        for rec in self:
            rec.child_count = len(rec.child_ids)

    def _compute_next_period_id(self):
        for rec in self:
            next_p = self.search([('previous_period_id', '=', rec.id)], limit=1)
            rec.next_period_id = next_p.id if next_p else False

    def _compute_period_statistics(self):
        """تجميع الإحصائيات بكفاءة عالية على مستوى الفترة"""
        for rec in self:
            rec.expected_accounts = 0
            rec.received_readings = 0
            rec.missing_readings = 0
            rec.images_ready = 0
            rec.pending_review = 0
            rec.approved_readings = 0
            rec.rejected_readings = 0
            rec.bills_generated = 0
            rec.billed_amount = 0.0
            rec.accounting_total = 0.0
            rec.collected_in_window = 0.0
            rec.outstanding_amount = 0.0
            rec.collection_rate = 0.0
            rec.exception_count = 0

            target_period = rec if rec.period_role == 'reading' else rec.reading_period_id
            if not target_period:
                continue

            # حسابات القراءات
            readings = self.env['utility.reading'].search([('date_range_id', '=', target_period.id)])
            rec.received_readings = len(readings)
            rec.pending_review = len(readings.filtered(lambda r: r.state == 'under_review'))
            rec.approved_readings = len(readings.filtered(lambda r: r.state in ('approved', 'billed')))
            rec.rejected_readings = len(readings.filtered(lambda r: r.state == 'draft' and r.remarks))
            rec.images_ready = len(readings.filtered(lambda r: bool(r.meter_image)))
            rec.exception_count = len(readings.filtered(lambda r: r.state == 'error' or bool(r.billing_error)))

            # حسابات الفواتير والتحصيل
            orders = self.env['sale.order'].search([('date_range_id', '=', target_period.id), ('state', '!=', 'cancel')])
            rec.bills_generated = len(orders)
            rec.billed_amount = sum(orders.mapped('amount_total'))
            
            invoices = orders.mapped('utility_move_ids').filtered(lambda m: m.state == 'posted')
            rec.accounting_total = sum(invoices.mapped('amount_total'))
            
            payments = self.env['account.payment'].search([
                ('utility_sale_order_id', 'in', orders.ids),
                ('state', '=', 'posted')
            ])
            rec.collected_in_window = sum(payments.mapped('amount'))
            rec.outstanding_amount = rec.billed_amount - rec.collected_in_window
            if rec.billed_amount > 0:
                rec.collection_rate = round((rec.collected_in_window / rec.billed_amount) * 100.0, 2)

    # ===== Model Constraints =====
    @api.constrains('consumption_start', 'consumption_end')
    def _check_consumption_dates(self):
        for rec in self:
            if rec.consumption_start and rec.consumption_end and rec.consumption_start > rec.consumption_end:
                raise ValidationError(_("تاريخ بداية الاستهلاك يجب أن يكون قبل أو يساوي تاريخ النهاية."))

    @api.constrains('reading_window_start', 'reading_window_end')
    def _check_reading_window_dates(self):
        for rec in self:
            if rec.reading_window_start and rec.reading_window_end and rec.reading_window_start > rec.reading_window_end:
                raise ValidationError(_("تاريخ بداية نافذة القراءة يجب أن يكون قبل تاريخ النهاية."))

    @api.constrains('period_role', 'reading_period_id')
    def _check_payment_reading_link(self):
        for rec in self:
            if rec.period_role == 'payment':
                if not rec.reading_period_id:
                    raise ValidationError(_("يجب ربط فترة السداد والتحصيل بفترة قراءة واستهلاك صريحة."))
                if rec.reading_period_id.period_role != 'reading':
                    raise ValidationError(_("فترة القراءة المرتبطة يجب أن تكون من دور 'دورة قراءة وفوترة'."))

    @api.constrains('region_ids', 'billing_cadence')
    def _check_region_cadence_consistency(self):
        for rec in self:
            if rec.region_ids:
                mismatched = rec.region_ids.filtered(lambda r: r.recurring_rule_type and r.recurring_rule_type != rec.billing_cadence)
                if mismatched:
                    names = ", ".join(mismatched.mapped('name'))
                    raise ValidationError(_(
                        "دورية المناطق التابعة (%s) لا تطابق دورية الفترة (%s)."
                    ) % (names, rec.billing_cadence))

    # ===== Audit Helper =====
    def _log_state_transition(self, old_state, new_state, reason=False):
        for rec in self:
            self.env['date.range.log'].sudo().create({
                'period_id': rec.id,
                'old_state': old_state,
                'new_state': new_state,
                'user_id': self.env.uid,
                'timestamp': fields.Datetime.now(),
                'reason': reason or _("تغيير حالة الدورة التشغيلية"),
                'workflow_id': rec.workflow_id,
                'workflow_run_id': rec.workflow_run_id,
            })

    # ===== State Machine Action Methods =====

    def action_open_reading(self):
        for rec in self:
            if rec.period_role != 'reading':
                raise ValidationError(_("هذا الإجراء ينطبق فقط على فترات القراءة."))
            old_s = rec.state
            rec.write({
                'state': 'reading_open',
                'opened_at': fields.Datetime.now(),
            })
            rec._log_state_transition(old_s, 'reading_open', _("فتح نافذة القراءة والرفع"))

    def action_close_reading(self):
        for rec in self:
            if rec.period_role != 'reading':
                raise ValidationError(_("هذا الإجراء ينطبق فقط على فترات القراءة."))
            old_s = rec.state
            rec.write({'state': 'reading_closed'})
            rec._log_state_transition(old_s, 'reading_closed', _("إغلاق نافذة القراءة العادية"))

    def action_start_review(self):
        for rec in self:
            old_s = rec.state
            rec.write({'state': 'reviewing'})
            rec._log_state_transition(old_s, 'reviewing', _("بدء مراجعة القراءات واللقطات"))

    def action_close_review(self):
        for rec in self:
            old_s = rec.state
            rec.write({'state': 'review_closed'})
            rec._log_state_transition(old_s, 'review_closed', _("إكمال مراجعة القراءات"))

    def action_start_billing(self):
        for rec in self:
            old_s = rec.state
            rec.write({'state': 'billing'})
            rec._log_state_transition(old_s, 'billing', _("بدء تحويل القراءات إلى فواتير"))

    def action_start_accounting(self):
        for rec in self:
            old_s = rec.state
            rec.write({'state': 'accounting'})
            rec._log_state_transition(old_s, 'accounting', _("بدء التظهير وترحيل الفواتير المحاسبية"))

    def _validate_period_closing_reconciliation(self):
        """فحص ومطابقة جميع متطلبات الإغلاق لضمان سلامة العمليات"""
        self.ensure_one()
        errors = []
        
        # 1. دفعات القراءات قيد الرفع والمعالجة
        batches = self.env['utility.reading.batch'].search([
            ('date_range_id', '=', self.id),
            ('state', 'in', ('uploaded', 'processing'))
        ])
        if batches:
            errors.append(_("توجد %d دفعة رفع قراءات ما زالت قيد المعالجة أو الرفع.") % len(batches))

        # 2. قراءات غير معتمدة أو بها أخطاء
        pending_readings = self.env['utility.reading'].search([
            ('date_range_id', '=', self.id),
            ('state', 'in', ('draft', 'under_review', 'queued', 'error'))
        ])
        if pending_readings:
            errors.append(_("توجد %d قراءة غير معتمدة أو بها أخطاء غير محلولة.") % len(pending_readings))

        # 3. قراءات معتمدة لم تُفوتر بعد
        unbilled_approved = self.env['utility.reading'].search([
            ('date_range_id', '=', self.id),
            ('reading_purpose', '=', 'periodic'),
            ('state', '=', 'approved'),
        ])
        if unbilled_approved:
            errors.append(_("توجد %d قراءة معتمدة لم يتم إنشاء فواتير لها بعد.") % len(unbilled_approved))

        # 4. فواتير كهرباء لم يتم تظهير فواتير محاسبية لها
        unposted_orders = self.env['sale.order'].search([
            ('date_range_id', '=', self.id),
            ('state', '!=', 'cancel'),
        ])
        for order in unposted_orders:
            if not order.utility_move_ids or any(m.state != 'posted' for m in order.utility_move_ids):
                errors.append(_("امر البيع %s لا يحتوي على فاتورة محاسبية مرحلة.") % order.name)

        if errors:
            raise ValidationError(_("لا يمكن إغلاق فترة القراءة بسبب الملاحظات التالية:\n- ") + "\n- ".join(errors))

    def action_close_period(self):
        for rec in self:
            if rec.period_role == 'reading':
                rec._validate_period_closing_reconciliation()
            old_s = rec.state
            rec.write({
                'state': 'closed',
                'closed_at': fields.Datetime.now(),
            })
            rec._log_state_transition(old_s, 'closed', _("إغلاق الفترة بعد استكمال المطابقة"))

    def action_lock_period(self):
        for rec in self:
            old_s = rec.state
            rec.write({
                'state': 'locked',
                'locked_at': fields.Datetime.now(),
            })
            rec._log_state_transition(old_s, 'locked', _("إقفال تاريخي نائي للفترة"))

    def action_open_payment(self):
        for rec in self:
            if rec.period_role != 'payment':
                raise ValidationError(_("هذا الإجراء ينطبق فقط على فترات التحصيل والتحصيل."))
            old_s = rec.state
            rec.write({
                'state': 'open',
                'opened_at': fields.Datetime.now(),
            })
            rec._log_state_transition(old_s, 'open', _("فتح نافذة التحصيل"))

    def action_close_payment(self):
        for rec in self:
            if rec.period_role != 'payment':
                raise ValidationError(_("هذا الإجراء ينطبق فقط على فترات التحصيل."))
            old_s = rec.state
            rec.write({'state': 'closed'})
            rec._log_state_transition(old_s, 'closed', _("إغلاق نافذة التحصيل"))

    def action_reconcile_payment(self):
        for rec in self:
            old_s = rec.state
            rec.write({'state': 'reconciled'})
            rec._log_state_transition(old_s, 'reconciled', _("إكمال مطابقة المقبوضات والتحصيل"))

    def action_reopen_period(self, reason="إعادة فتح استثنائي"):
        for rec in self:
            old_s = rec.state
            new_s = 'reading_open' if rec.period_role == 'reading' else 'open'
            rec.write({'state': new_s})
            rec._log_state_transition(old_s, new_s, reason)


class DateRangeLog(models.Model):
    _name = 'date.range.log'
    _description = 'سجل تدقيق وتغييرات فترات الفوترة'
    _order = 'timestamp desc, id desc'

    period_id = fields.Many2one('date.range', string="الفترة", required=True, ondelete='cascade', index=True)
    old_state = fields.Char(string="الحالة السابقة")
    new_state = fields.Char(string="الحالة الجديدة")
    user_id = fields.Many2one('res.users', string="المستخدم", default=lambda self: self.env.user)
    timestamp = fields.Datetime(string="التاريخ والوقت", default=fields.Datetime.now)
    reason = fields.Text(string="السبب / البيان")
    workflow_id = fields.Char(string="معرف Temporal Workflow")
    workflow_run_id = fields.Char(string="معرف Temporal Run")
