from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityReading(models.Model):
    _name = 'utility.reading'
    _description = 'قراءة عداد'
    _rec_name = 'reading_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reading_date desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    reading_id = fields.Char('رقم القراءة', default=lambda self: _('جديد'), readonly=True)
    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, index=True)
    customer_id = fields.Many2one('utility.customer', 'العميل/العقد', related='meter_id.customer_id', store=True, index=True)
    account_id = fields.Many2one('utility.customer', 'الحساب', related='customer_id', store=True)
    reading_date = fields.Datetime('تاريخ القراءة', default=fields.Datetime.now, required=True)
    reading_value = fields.Float('قيمة القراءة', required=True)
    consumption = fields.Float('الاستهلاك', compute='_compute_consumption', store=True)
    reading_category = fields.Selection([
        ('customer', 'مشترك'),
        ('transformer', 'محول / خلية'),
        ('feeder', 'فيدر'),
    ], string='تصنيف القراءة', default='customer', required=True)
    transformer_id = fields.Many2one('utility.transformer', 'المحول', related='meter_id.transformer_id', store=True)
    is_private_transformer = fields.Boolean('محول خاص', related='transformer_id.is_private', store=True)
    feeder_id = fields.Many2one('utility.feeder', 'الفيدر', related='meter_id.feeder_id', store=True)
    reading_type = fields.Selection([
        ('manual', 'يدوي'),
        ('estimated', 'تقديري'),
        ('ami', 'قراءة تلقائية (AMI)'),
    ], string='نوع القراءة', default='manual')
    is_estimated = fields.Boolean('تقديرية', default=False)
    meter_image = fields.Binary('صورة العداد', attachment=True,
        help='الصورة الملتقطة للعداد وقت القراءة')
    meter_image_secondary = fields.Binary('صورة إضافية', attachment=True)
    image_state = fields.Selection([
        ('clear', 'واضحة'),
        ('not_clear', 'غير واضحة'),
        ('not_same', 'لا تطابق العداد'),
        ('none', 'بدون صورة'),
        ('replace', 'عداد مركب حديثاً'),
        ('loss_read', 'قراءة مفقودة'),
    ], string='حالة الصورة', default='none',
        help='حالة فحص الصورة من قبل المراجع')
    attachment_id = fields.Many2one('ir.attachment', string='ملف المرفق الرسمي')
    reviewer_id = fields.Many2one('res.users', 'المراجع',
        readonly=True, tracking=True)
    review_date = fields.Datetime('تاريخ المراجعة', readonly=True)
    review_notes = fields.Text('ملاحظات المراجعة')
    rejection_reason = fields.Text('سبب الرفض')
    is_validated = fields.Boolean('تم التحقق', default=False)
    validator_id = fields.Many2one('res.users', 'المُتحقّق')
    previous_reading = fields.Float('القراءة السابقة', compute='_compute_previous_reading', store=True)
    previous_reading_date = fields.Datetime('تاريخ القراءة السابقة', compute='_compute_previous_reading', store=True)
    consumption_difference = fields.Float('فرق الاستهلاك',
        compute='_compute_consumption_analysis', store=True)
    consumption_diff_percentage = fields.Float('نسبة الفرق %',
        compute='_compute_consumption_analysis', store=True)
    consumption_alert = fields.Selection([
        ('normal', 'طبيعي'),
        ('high', 'مرتفع'),
        ('negative', 'سلبي'),
        ('zero', 'صفر'),
    ], compute='_compute_consumption_analysis', store=True, string='حالة الاستهلاك')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('under_review', 'قيد المراجعة'),
        ('approved', 'معتمدة'),
        ('queued', 'في طابور الفوترة'),
        ('billed', 'مفوترة'),
        ('error', 'خطأ'),
    ], string='الحالة', default='draft', tracking=True, index=True)
    date_range_id = fields.Many2one('date.range', string="الفترة", index=True)
    remarks = fields.Text('ملاحظات')
    billing_error = fields.Text('خطأ الفوترة', readonly=True)
    reading_source = fields.Char('مصدر القراءة')

    _sql_constraints = [
        ('unique_meter_reading_date',
         'unique(meter_id, reading_date)',
         'يوجد قراءة لنفس العداد في نفس التاريخ!'),
    ]

    STATE_EDITABLE = {
        'draft': {'meter_id', 'reading_date', 'reading_value', 'reading_category',
                  'reading_type', 'is_estimated', 'meter_image', 'meter_image_secondary',
                  'image_state', 'rejection_reason', 'remarks', 'date_range_id',
                  'reading_source', 'active'},
        'under_review': {'meter_image', 'meter_image_secondary', 'image_state',
                         'review_notes', 'rejection_reason', 'state'},
        'approved': {'rejection_reason', 'state', 'active'},
        'queued': {'state'},
        'billed': {'active', 'remarks'},
        'error': {'reading_date', 'reading_value', 'meter_image', 'meter_image_secondary',
                  'image_state', 'remarks', 'date_range_id', 'state'},
    }

    def write(self, vals):
        if self.env.context.get('_bypass_reading_protection'):
            return super().write(vals)
        bypass_states = {'state', 'active', 'remarks', 'rejection_reason'}
        for r in self:
            editable = self.STATE_EDITABLE.get(r.state, set())
            changed = set(vals) - bypass_states
            if changed and not changed.issubset(editable):
                forbidden = changed - editable
                raise ValidationError(
                    'لا يمكن تعديل الحقول التالية في حالة "%s": %s.\n'
                    'الحقول المسموحة: %s'
                    % (r.state, ', '.join(forbidden), ', '.join(editable))
                )
        return super().write(vals)

    # ── FIX-2: منع أكثر من قراءة قابلة للفوترة لنفس العداد والفترة ──────────
    @api.constrains('meter_id', 'date_range_id', 'state', 'reading_category')
    def _check_unique_billable_reading_per_period(self):
        """قراءة واحدة قابلة للفوترة لكل عداد + فترة — يمنع تكرار الفوترة."""
        for r in self:
            is_billable = (
                r.reading_category == 'customer'
                or (r.reading_category == 'transformer' and r.is_private_transformer)
            )
            if not is_billable or not r.date_range_id or r.state == 'error':
                continue
            duplicate = self.search([
                ('meter_id', '=', r.meter_id.id),
                ('date_range_id', '=', r.date_range_id.id),
                ('reading_category', '=', r.reading_category),
                ('state', 'not in', ['error']),
                ('id', '!=', r.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    'يوجد قراءة أخرى للعداد [%s] في نفس فترة الفوترة [%s].\n'
                    'لا يُسمح بأكثر من قراءة واحدة قابلة للفوترة لنفس العداد والفترة.'
                    % (r.meter_id.meter_number, r.date_range_id.name)
                )

    @api.depends('reading_value', 'previous_reading')
    def _compute_consumption(self):
        for r in self:
            r.consumption = r.reading_value - (r.previous_reading or 0.0)

    @api.depends('consumption', 'meter_id')
    def _compute_consumption_analysis(self):
        meters = self.mapped('meter_id')
        approved_map = {}
        if meters:
            approved_readings = self.search([
                ('meter_id', 'in', meters.ids),
                ('state', '=', 'approved'),
                ('id', 'not in', self.ids),
            ], order='reading_date desc')
            for a in approved_readings:
                approved_map.setdefault(a.meter_id.id, []).append(a)

        for r in self:
            if r.consumption <= 0:
                r.consumption_alert = 'zero' if r.consumption == 0 else 'negative'
                r.consumption_difference = 0
                r.consumption_diff_percentage = 0
                continue
            candidates = approved_map.get(r.meter_id.id, [])
            last_approved = candidates[0] if candidates else False
            if last_approved and last_approved.consumption > 0:
                diff = r.consumption - last_approved.consumption
                r.consumption_difference = diff
                r.consumption_diff_percentage = (diff / last_approved.consumption) * 100
                r.consumption_alert = 'high' if abs(r.consumption_diff_percentage) > 50 else 'normal'
            else:
                r.consumption_difference = 0
                r.consumption_diff_percentage = 0
                r.consumption_alert = 'normal'

    @api.depends('meter_id', 'reading_date')
    def _compute_previous_reading(self):
        meters = self.mapped('meter_id')
        prev_map = {}
        if meters:
            all_prev = self.search([
                ('meter_id', 'in', meters.ids),
                ('state', 'in', ['approved', 'billed']),
            ], order='meter_id, reading_date desc')
            for p in all_prev:
                prev_map.setdefault(p.meter_id.id, []).append(p)

        for r in self:
            candidates = prev_map.get(r.meter_id.id, [])
            found = False
            for p in candidates:
                if p.reading_date < r.reading_date and p.id != r.id:
                    r.previous_reading = p.reading_value
                    r.previous_reading_date = p.reading_date
                    found = True
                    break
            if not found:
                r.previous_reading = 0.0
                r.previous_reading_date = False

    def action_submit_review(self):
        for r in self:
            if r.state != 'draft':
                raise ValidationError('يمكن إرسال القراءات المسودة فقط للمراجعة!')

            is_billable = (r.reading_category == 'customer' or (r.reading_category == 'transformer' and r.is_private_transformer))

            if not r.meter_image and is_billable:
                raise ValidationError('يجب رفع صورة العداد قبل إرسال القراءة للمراجعة!')

            r.write({
                'reading_source': r.reading_source or f'manual_{fields.Datetime.now()}',
            })

            if is_billable:
                r.state = 'under_review'
            else:
                r.state = 'approved'
                r.is_validated = True
                r.validator_id = self.env.user.id
                r.reviewer_id = self.env.user.id
                r.review_date = fields.Datetime.now()

    def action_approve(self):
        for r in self:
            if r.state != 'under_review':
                raise ValidationError('يمكن الموافقة على القراءات قيد المراجعة فقط!')

            # FIX-4: منع اعتماد قراءة بالاستهلاك سالب للقراءات القابلة للفوترة
            is_billable = (
                r.reading_category == 'customer'
                or (r.reading_category == 'transformer' and r.is_private_transformer)
            )
            if is_billable and r.consumption < 0:
                raise ValidationError(
                    'لا يمكن اعتماد قراءة باستهلاك سالب (%.2f). '
                    'تحقق من صحة القراءة أو أنشئ تسوية.'
                    % r.consumption
                )

            r.write({
                'state': 'approved',
                'is_validated': True,
                'validator_id': self.env.user.id,
                'reviewer_id': self.env.user.id,
                'review_date': fields.Datetime.now(),
            })

            # FIX-3: تحديث آخر قراءة على الحساب عند الاعتماد
            if r.account_id:
                current_last = r.account_id.last_reading_date
                if not current_last or r.reading_date > current_last:
                    r.account_id.sudo().write({
                        'last_reading_date': r.reading_date,
                        'last_reading_value': r.reading_value,
                    })

    def action_reject(self):
        for r in self:
            # FIX-1: منع رفض قراءة مفوترة — يجب إلغاء الفاتورة أولاً أو استخدام تسوية
            if r.state == 'billed':
                raise ValidationError(
                    'لا يمكن رفض قراءة مفوترة مباشرةً.\n'
                    'قم بإلغاء الفاتورة المرتبطة أولاً، '
                    'أو استخدم نموذج تسوية القراءات لتعديل القيمة.'
                )
            if r.state not in ('under_review', 'approved'):
                raise ValidationError('يمكن رفض القراءات قيد المراجعة أو المعتمدة فقط!')
            r.write({
                'state': 'draft',
                'rejection_reason': r.rejection_reason or 'مرفوضة من قبل المراجع',
            })

    def action_approve_batch(self):
        readings = self.filtered(lambda r: r.state == 'under_review')
        readings.action_approve()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reading_id', _('جديد')) == _('جديد'):
                vals['reading_id'] = self.env['ir.sequence'].next_by_code('utility.reading') or _('جديد')
        return super().create(vals_list)
