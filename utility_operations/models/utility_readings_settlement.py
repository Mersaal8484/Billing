import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityReadingSettlement(models.Model):
    """تسوية قراءة — أداة التصحيح التقني للقراءات المفوترة.

    هذا النموذج يسجّل طلب التصحيح التقني فقط.
    لا يعدّل قيمة القراءة الأصلية في أي حالة.
    التأثير المالي (إشعار دائن / فاتورة إضافية) يُعالَج من قِبَل
    utility_billing عبر utility.billing.adjustment.

    دورة الحياة:
        draft → submitted → technically_approved → processed
        [أي حالة غير processed] → cancelled
    """
    _name = 'utility.reading.settlement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'تسوية قراءة (تصحيح تقني)'
    _rec_name = 'name'
    _order = 'create_date desc'

    # ── تعريف ─────────────────────────────────────────────────────────────────
    name = fields.Char(
        'رقم التسوية',
        default=lambda self: _('New'),
        readonly=True,
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True, index=True,
        default=lambda self: self.env.company,
    )
    reading_id = fields.Many2one(
        'utility.reading', 'القراءة المستهدفة',
        required=True, index=True, ondelete='restrict',
        help='يجب أن تكون القراءة بحالة مفوترة (billed) لإجراء تصحيح تقني.',
    )
    meter_id = fields.Many2one(
        'utility.meter',
        related='reading_id.meter_id', store=True, index=True,
    )
    account_id = fields.Many2one(
        'utility.customer',
        related='reading_id.account_id', store=True, index=True,
    )

    # ── القيم الأصلية والمصحّحة ──────────────────────────────────────────────
    original_reading_value = fields.Float(
        'قيمة القراءة الأصلية',
        readonly=True,
        help='القيمة المسجّلة تاريخياً — لا تُعدَّل أبداً.',
    )
    corrected_reading_value = fields.Float(
        'القراءة المصحّحة',
        required=True,
        help='القيمة الصحيحة التي كان يجب أن تكون عليها القراءة.',
    )
    original_consumption = fields.Float(
        'الاستهلاك الأصلي (kWh)',
        readonly=True,
    )

    @api.depends('corrected_reading_value', 'reading_id.previous_reading')
    def _compute_corrected_consumption(self):
        for rec in self:
            if rec.reading_id:
                prev = rec.reading_id.previous_reading or 0.0
                rec.corrected_consumption = max(0.0, rec.corrected_reading_value - prev)
                rec.delta_consumption = rec.corrected_consumption - (rec.original_consumption or 0.0)
            else:
                rec.corrected_consumption = 0.0
                rec.delta_consumption = 0.0

    corrected_consumption = fields.Float(
        'الاستهلاك المصحّح (kWh)',
        compute='_compute_corrected_consumption', store=True,
    )
    delta_consumption = fields.Float(
        'فرق الاستهلاك (kWh)',
        compute='_compute_corrected_consumption', store=True,
        help='موجب = استهلاك أعلى من الأصلي، سالب = استهلاك أقل.',
    )
    reason = fields.Text('سبب التصحيح التقني', required=True)

    # ── دورة الحياة ────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('submitted', 'مُقدَّم للمراجعة التقنية'),
        ('technically_approved', 'مُعتمَد تقنياً'),
        ('processed', 'تمت الإحالة للفوترة'),
        ('cancelled', 'ملغى'),
    ], string='الحالة', default='draft', readonly=True, tracking=True, copy=False)

    # ── سجل الإجراءات ──────────────────────────────────────────────────────────
    submitted_by_id = fields.Many2one(
        'res.users', 'مُقدِّم التصحيح', readonly=True, copy=False,
    )
    submitted_date = fields.Datetime('تاريخ التقديم', readonly=True, copy=False)
    approved_by_id = fields.Many2one(
        'res.users', 'المشرف التقني المعتمِد', readonly=True, copy=False,
    )
    approved_date = fields.Datetime('تاريخ الاعتماد التقني', readonly=True, copy=False)
    processed_by_id = fields.Many2one(
        'res.users', 'منفّذ الإحالة', readonly=True, copy=False,
    )
    processed_date = fields.Datetime('تاريخ الإحالة', readonly=True, copy=False)
    cancel_reason = fields.Text('سبب الإلغاء', copy=False)
    cancelled_by_id = fields.Many2one(
        'res.users', 'من ألغى', readonly=True, copy=False,
    )
    cancelled_date = fields.Datetime('تاريخ الإلغاء', readonly=True, copy=False)

    # ── ربط المستند المحاسبي (يُملأ من utility_billing) ──────────────────────
    correction_move_id = fields.Many2one(
        'account.move', 'مستند التصحيح المحاسبي', readonly=True,
        help='إشعار دائن أو فاتورة إضافية نتجت عن التصحيح — يُعبَّأ بواسطة وحدة الفوترة.',
    )

    # ── تقييد التكرار ─────────────────────────────────────────────────────────
    _sql_constraints = [
        ('unique_reading_active_settlement',
         'exclude (reading_id WITH =) WHERE (state NOT IN (\'cancelled\'))',
         'لا يمكن وجود أكثر من تسوية تقنية نشطة للقراءة ذاتها.'),
    ]

    @api.onchange('reading_id')
    def _onchange_reading_id(self):
        if self.reading_id:
            self.original_reading_value = self.reading_id.reading_value
            self.original_consumption = self.reading_id.consumption

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = seq.next_by_code('utility.reading.settlement') or _('New')
            if not vals.get('company_id') and vals.get('reading_id'):
                reading = self.env['utility.reading'].browse(vals['reading_id'])
                if reading.meter_id:
                    vals['company_id'] = reading.meter_id.company_id.id or self.env.company.id
        return super().create(vals_list)

    # ── إجراءات دورة الحياة ───────────────────────────────────────────────────

    def action_submit(self):
        """تقديم طلب التصحيح التقني — يتحقق أن القراءة مفوترة فعلاً."""
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('يمكن تقديم التسويات المسودة فقط.'))
            if rec.reading_id.state != 'billed':
                raise ValidationError(_(
                    'القراءة %s ليست بحالة مفوترة (billed). الحالة الحالية: %s.'
                ) % (rec.reading_id.reading_id, rec.reading_id.state))
            if not rec.reason or not rec.reason.strip():
                raise ValidationError(_('يجب إدخال سبب واضح للتصحيح التقني.'))
            rec.write({
                'state': 'submitted',
                'original_reading_value': rec.reading_id.reading_value,
                'original_consumption': rec.reading_id.consumption,
                'submitted_by_id': self.env.user.id,
                'submitted_date': fields.Datetime.now(),
            })
            rec.message_post(body=_('تم تقديم طلب التصحيح التقني للمراجعة.'))

    def action_technically_approve(self):
        """اعتماد تقني — لا يجوز أن يعتمد من قدّم الطلب."""
        for rec in self:
            if rec.state != 'submitted':
                raise ValidationError(_('يمكن اعتماد التسويات المُقدَّمة فقط.'))
            if rec.submitted_by_id == self.env.user:
                raise AccessError(_(
                    'لا يمكن لمن قدّم طلب التصحيح (%s) أن يعتمده تقنياً.'
                ) % self.env.user.name)
            rec.write({
                'state': 'technically_approved',
                'approved_by_id': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            rec.message_post(body=_('تم الاعتماد التقني للتصحيح.'))

    def action_process(self):
        """إحالة التصحيح إلى وحدة الفوترة لمعالجة الأثر المالي.

        لا يُعدِّل هذا الإجراء قيمة القراءة الأصلية أبداً.
        يُشغِّل فقط hook الإحالة (_on_settlement_processed) ليتولاها utility_billing.
        """
        for rec in self:
            if rec.state != 'technically_approved':
                raise ValidationError(_(
                    'يمكن إحالة التسويات المعتمدة تقنياً فقط.'
                ))
            # سجل سمعي على القراءة الأصلية دون أي تعديل في القيمة
            rec.reading_id.message_post(body=_(
                'تصحيح تقني معتمد: القراءة الأصلية=%.2f → المصحّحة=%.2f '
                '(فرق الاستهلاك: %+.2f kWh). '
                'التسوية: %s. القيمة الأصلية محفوظة بدون تعديل.'
            ) % (
                rec.original_reading_value,
                rec.corrected_reading_value,
                rec.delta_consumption,
                rec.name,
            ))
            # سجل العداد
            if rec.meter_id:
                self.env['utility.meter.log']._create_log(
                    rec.meter_id,
                    'settlement',
                    _(
                        'تصحيح تقني: %.2f → %.2f (فرق: %+.2f kWh). '
                        'السبب: %s'
                    ) % (
                        rec.original_reading_value,
                        rec.corrected_reading_value,
                        rec.delta_consumption,
                        rec.reason,
                    ),
                    ref_record=rec,
                )
            rec.write({
                'state': 'processed',
                'processed_by_id': self.env.user.id,
                'processed_date': fields.Datetime.now(),
            })
            rec.message_post(body=_('تمت إحالة التصحيح التقني إلى وحدة الفوترة.'))
            # hook موسّع — utility_billing يتولى إنشاء billing.adjustment
            rec._on_settlement_processed()

    def _on_settlement_processed(self):
        """Hook موسّع: تستدعيه وحدة utility_billing لإنشاء utility.billing.adjustment.

        لا يحتوي على منطق هنا لتجنّب الاعتماد العكسي:
            utility_operations ← utility_billing  ← محظور
        """
        pass

    def action_cancel(self):
        """إلغاء التسوية من أي حالة غير processed."""
        for rec in self:
            if rec.state == 'processed':
                raise ValidationError(_(
                    'لا يمكن إلغاء تسوية تمت إحالتها (processed). '
                    'استخدم مستند عكس في وحدة الفوترة إن لزم الأمر.'
                ))
            rec.write({
                'state': 'cancelled',
                'cancelled_by_id': self.env.user.id,
                'cancelled_date': fields.Datetime.now(),
            })
            rec.message_post(body=_(
                'تم إلغاء التسوية. السبب: %s'
            ) % (rec.cancel_reason or _('لم يُحدَّد سبب.')))
