from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityReading(models.Model):
    _name = 'utility.reading'
    _description = 'قراءة عداد'
    _rec_name = 'reading_id'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'utility.dropdown.mixin']
    _order = 'reading_date desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    reading_id = fields.Char('رقم القراءة', default=lambda self: _('جديد'), readonly=True)
    meter_serial_scan = fields.Char('مسح العداد (باركود)', store=False, help="استخدم الكاميرا لمسح رقم العداد وجلبه تلقائياً")
    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, index=True)
    account_id = fields.Many2one(
        'utility.customer', 'الحساب', index=True,
        check_company=True, ondelete='restrict',
        help='حساب المشترك المثبت تاريخياً وقت إنشاء القراءة.')
    customer_id = fields.Many2one(
        'utility.customer', 'العميل/العقد', related='account_id',
        store=True, index=True, readonly=True)
    reading_date = fields.Datetime('تاريخ القراءة', default=fields.Datetime.now, required=True)
    reading_value = fields.Float('قيمة القراءة', required=True)
    raw_consumption = fields.Float('الاستهلاك الخام', compute='_compute_consumption', store=True)
    consumption = fields.Float('الاستهلاك', compute='_compute_consumption', store=True)
    meter_multiplier = fields.Float('معامل الضرب وقت القراءة', default=1.0, required=True)
    reading_purpose = fields.Selection([
        ('opening', 'افتتاحية'), ('periodic', 'دورية'),
        ('replacement_closing', 'ختامية استبدال'),
    ], string='غرض القراءة', default='periodic', required=True, index=True, tracking=True)
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
    ], string='طريقة أخذ القراءة', default='manual')
    is_estimated = fields.Boolean('تقديرية', default=False)
    is_initial_reading = fields.Boolean('قراءة افتتاحية', default=False)
    replacement_id = fields.Many2one('utility.meter.replacement', 'عملية الاستبدال', index=True, check_company=True, ondelete='restrict')
    billing_anchor_id = fields.Many2one('utility.reading', 'القراءة الدورية المرتبطة', index=True, readonly=True, copy=False, ondelete='restrict')
    billing_component_ids = fields.One2many('utility.reading', 'billing_anchor_id', 'قراءات الإغلاق المضمّنة')
    included_sale_order_id = fields.Many2one('sale.order', 'الفاتورة المتضمنة', index=True, readonly=True, copy=False, ondelete='restrict')
    carried_consumption = fields.Float('استهلاك مرحل', compute='_compute_billing_consumption', store=True)
    billing_consumption = fields.Float('استهلاك الفاتورة', compute='_compute_billing_consumption', store=True)
    image_asset_id = fields.Many2one('utility.media.asset', string='Meter Image Asset', ondelete='set null', index=True)
    meter_image = fields.Binary('صورة العداد (توافقي)', compute='_compute_meter_image', inverse='_inverse_meter_image', store=False,
                                help='حقل توافقي غير مخزن — التخزين الأصيل ممركز في image_asset_id')
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

    @api.depends('image_asset_id', 'image_asset_id.original_attachment_id', 'attachment_id')
    def _compute_meter_image(self):
        for r in self:
            if r.image_asset_id and r.image_asset_id.original_attachment_id:
                r.meter_image = r.image_asset_id.original_attachment_id.datas
            elif r.attachment_id:
                r.meter_image = r.attachment_id.datas

    def _inverse_meter_image(self):
        for r in self:
            if r.meter_image and not r.image_asset_id:
                asset = self.env['utility.media.service'].sudo().store_media(
                    file_data=r.meter_image,
                    filename=f"reading_{r.id or 'legacy'}.jpg",
                    mimetype='image/jpeg',
                    reading_id=r.id if isinstance(r.id, int) else False,
                    asset_type='meter_reading'
                )
                r.image_asset_id = asset.id
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
    available_open_reading_period_ids = fields.Many2many('date.range', compute='_compute_available_open_reading_period_ids')
    date_range_id = fields.Many2one('date.range', string="الفترة", index=True)
    remarks = fields.Text('ملاحظات')
    billing_error = fields.Text('خطأ الفوترة', readonly=True)
    reading_source = fields.Char('مصدر القراءة')

    def init(self):
        """Backfill stable accounts and legacy opening-reading purposes on upgrade."""
        self.env.flush_all()
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS utility_reading_meter_date_idx
            ON utility_reading (meter_id, reading_date DESC)
        """)
        self.env.cr.execute("""
            UPDATE utility_reading reading
               SET account_id = meter.customer_id
              FROM utility_meter meter
             WHERE reading.meter_id = meter.id
               AND reading.account_id IS NULL
               AND meter.customer_id IS NOT NULL
        """)
        self.env.cr.execute("""
            UPDATE utility_reading
               SET reading_purpose = 'opening'
             WHERE is_initial_reading = TRUE
               AND reading_purpose != 'opening'
        """)

    @api.onchange('meter_serial_scan')
    def _onchange_meter_serial_scan(self):
        if self.meter_serial_scan:
            meter = self.env['utility.meter'].search([
                ('meter_number', '=', self.meter_serial_scan)
            ], limit=1)
            
            if not meter:
                meter = self.env['utility.meter'].search([
                    ('serial_number', '=', self.meter_serial_scan)
                ], limit=1)

            if meter:
                self.meter_id = meter.id
                self.meter_serial_scan = False
                return {
                    'warning': {
                        'title': _('نجاح'),
                        'message': _('تم العثور على العداد (%s) بنجاح.') % meter.display_name,
                        'type': 'notification',
                    }
                }
            else:
                return {
                    'warning': {
                        'title': _('غير موجود'),
                        'message': _('لم يتم العثور على عداد يحمل الرقم: %s') % self.meter_serial_scan,
                    }
                }


    @api.onchange('meter_id')
    def _onchange_meter_account(self):
        """Snapshot the account and multiplier selected with the meter."""
        if self.meter_id:
            self.account_id = self.meter_id.customer_id
            self.meter_multiplier = self.meter_id.multiplier or 1.0

    @api.onchange('reading_purpose')
    def _onchange_reading_purpose(self):
        if self.reading_purpose != 'periodic':
            self.date_range_id = False
        else:
            if not self.date_range_id and self.available_open_reading_period_ids:
                self.date_range_id = self.available_open_reading_period_ids[0].id
        self.is_initial_reading = self.reading_purpose == 'opening'

    @api.onchange('reading_category')
    def _onchange_reading_category(self):
        if self.reading_category == 'customer':
            self.transformer_id = False
            self.feeder_id = False
        elif self.reading_category == 'transformer':
            self.feeder_id = False
        elif self.reading_category == 'feeder':
            self.transformer_id = False

    reading_history_count = fields.Integer('عدد القراءات السابقة', compute='_compute_reading_history_count')

    @api.depends('meter_id')
    def _compute_reading_history_count(self):
        for r in self:
            if r.meter_id:
                domain = [('meter_id', '=', r.meter_id.id)]
                if r.id and isinstance(r.id, int):
                    domain.append(('id', '!=', r.id))
                r.reading_history_count = self.search_count(domain)
            else:
                r.reading_history_count = 0

    def action_view_reading_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('سجل القراءات - %s') % self.meter_id.meter_number,
            'res_model': 'utility.reading',
            'view_mode': 'tree,form',
            'domain': [('meter_id', '=', self.meter_id.id), ('id', '!=', self.id)],
            'context': {'create': False},
        }

    _sql_constraints = [
        ('unique_meter_reading_date',
         'unique(meter_id, reading_date)',
         'يوجد قراءة لنفس العداد في نفس التاريخ!'),
    ]

    STATE_EDITABLE = {
        'draft': {'meter_id', 'reading_date', 'reading_value', 'reading_category',
                  'reading_type', 'reading_purpose', 'account_id', 'meter_multiplier',
                  'is_estimated', 'is_initial_reading', 'replacement_id', 'meter_image', 'meter_image_secondary',
                  'image_state', 'rejection_reason', 'remarks', 'date_range_id',
                  'reading_source', 'active', 'is_validated', 'validator_id',
                  'reviewer_id', 'review_date'},
        'under_review': {'meter_image', 'meter_image_secondary', 'image_state',
                          'review_notes', 'rejection_reason', 'state',
                          'is_validated', 'validator_id', 'reviewer_id', 'review_date'},
        'approved': {'rejection_reason', 'state', 'active', 'attachment_id', 'date_range_id',
                     'billing_error', 'billing_anchor_id', 'included_sale_order_id'},
        'queued': {'state', 'attachment_id', 'billing_error'},
        'billed': {'active', 'remarks', 'billing_error'},
        'error': {'reading_date', 'reading_value', 'meter_image', 'meter_image_secondary',
                  'image_state', 'remarks', 'date_range_id', 'state', 'billing_error'},
    }

    # ── FIX-2: منع أكثر من قراءة قابلة للفوترة لنفس العداد والفترة ──────────
    @api.constrains('account_id', 'date_range_id', 'state', 'reading_category', 'reading_purpose')
    def _check_unique_billable_reading_per_period(self):
        """قراءة واحدة قابلة للفوترة لكل عداد + فترة — يمنع تكرار الفوترة."""
        for r in self:
            is_billable = (
                r.reading_category == 'customer'
                or (r.reading_category == 'transformer' and r.is_private_transformer)
            )
            if (not is_billable or r.reading_purpose != 'periodic'
                    or not r.date_range_id or r.state == 'error'):
                continue
            duplicate = self.search([
                ('account_id', '=', r.account_id.id),
                ('date_range_id', '=', r.date_range_id.id),
                ('reading_purpose', '=', 'periodic'),
                ('reading_category', '=', r.reading_category),
                ('state', 'not in', ['error']),
                ('id', '!=', r.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    'يوجد قراءة دورية أخرى للحساب [%s] في فترة الفوترة [%s].\n'
                    'لا يُسمح بأكثر من قراءة دورية واحدة للحساب والفترة، حتى عند استبدال العداد.'
                    % (r.account_id.display_name, r.date_range_id.name)
                )

    @api.constrains('reading_purpose', 'date_range_id', 'replacement_id', 'billing_anchor_id', 'account_id', 'reading_date')
    def _check_reading_purpose_rules(self):
        """Enforce period, replacement, and billing-anchor invariants."""
        for reading in self:
            is_billable = (reading.reading_category == 'customer' or (reading.reading_category == 'transformer' and reading.is_private_transformer))
            if is_billable and not reading.account_id:
                raise ValidationError(_('القراءة القابلة للفوترة تتطلب حساب مشترك.'))
            if is_billable and reading.reading_purpose == 'periodic':
                if not reading.date_range_id:
                    raise ValidationError(_('القراءة الدورية تتطلب تحديد الفترة المفتوحة للقراءة بحسب العقد.'))
                period = reading.date_range_id
                expected = reading.account_id._get_effective_billing_period()
                if period.period_role and period.period_role != 'reading':
                    raise ValidationError(_('فترة القراءة الدورية يجب أن تكون من نوع قراءات.'))
                cadence = period.billing_cadence or getattr(period, 'billing_period', False)
                if expected and cadence and cadence != expected:
                    raise ValidationError(_(
                        'دورية الفترة المختارة (%s) لا تطابق دورية المشترك (%s).')
                        % (cadence, expected))
                if not period.is_current_period:
                    raise ValidationError(_(
                        'الفترة الصحيحة لهذه القراءة غير مفعلة حالياً: %s.') % period.name)
            if reading.reading_purpose != 'periodic' and reading.date_range_id:
                raise ValidationError(_('الفترة مسموحة للقراءة الدورية فقط.'))
            if reading.reading_purpose == 'replacement_closing' and not reading.replacement_id:
                raise ValidationError(_('القراءة الختامية تتطلب عملية استبدال مرتبطة.'))
            anchor = reading.billing_anchor_id
            if anchor and (anchor.reading_purpose != 'periodic' or anchor.account_id != reading.account_id or anchor.reading_date < reading.reading_date):
                raise ValidationError(_('يجب أن تكون قراءة الربط دورية ولاحقة ومن حساب المشترك نفسه.'))

    @api.depends('account_id.contract_template_id.recurring_rule_type', 'account_id.area_id.recurring_rule_type', 'account_id.region_id.recurring_rule_type')
    def _compute_available_open_reading_period_ids(self):
        for reading in self:
            account = reading.account_id
            billing_period = account._get_effective_billing_period() if account else False
            domain = self._get_open_period_domain(
                work_type='readings', billing_period=billing_period)
            reading.available_open_reading_period_ids = self.env['date.range'].search(domain)
    @api.onchange('account_id', 'meter_id', 'reading_purpose')
    def _onchange_account_id_date_range(self):
        available_periods = self.available_open_reading_period_ids
        if self.date_range_id and self.date_range_id not in available_periods:
            self.date_range_id = False
        if self.reading_purpose == 'periodic' and not self.date_range_id and available_periods:
            self.date_range_id = available_periods[0].id
        return {'domain': {'date_range_id': [('id', 'in', available_periods.ids)]}}

    @api.depends('reading_value', 'previous_reading', 'is_initial_reading', 'reading_purpose', 'meter_multiplier')
    def _compute_consumption(self):
        for r in self:
            if r.is_initial_reading or r.reading_purpose == 'opening':
                r.raw_consumption = 0.0
                r.consumption = 0.0
            else:
                raw = r.reading_value - (r.previous_reading or 0.0)
                r.raw_consumption = raw
                r.consumption = raw * (r.meter_multiplier or 1.0)

    @api.depends('consumption', 'reading_purpose', 'billing_component_ids.consumption')
    def _compute_billing_consumption(self):
        for reading in self:
            if reading.reading_purpose == 'periodic':
                reading.carried_consumption = sum(reading.billing_component_ids.mapped('consumption'))
                reading.billing_consumption = reading.consumption + reading.carried_consumption
            else:
                reading.carried_consumption = 0.0
                reading.billing_consumption = 0.0

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
                r.write({
                    'state': 'approved',
                    'is_validated': True,
                    'validator_id': self.env.user.id,
                    'reviewer_id': self.env.user.id,
                    'review_date': fields.Datetime.now(),
                })

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
            # تحديث آخر قراءة في العداد
            if r.meter_id:
                r.meter_id._update_last_reading()

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

    def write(self, vals):
        if not self.env.context.get('_bypass_reading_protection'):
            bypass_fields = {'state', 'active', 'remarks', 'rejection_reason'}
            for reading in self:
                editable = self.STATE_EDITABLE.get(reading.state, set())
                changed = set(vals) - bypass_fields
                if changed and not changed.issubset(editable):
                    forbidden = changed - editable
                    raise ValidationError(_(
                        'لا يمكن تعديل الحقول التالية في حالة %(state)s: %(fields)s') % {
                            'state': reading.state,
                            'fields': ', '.join(sorted(forbidden)),
                        })
        meters = self.mapped('meter_id')
        res = super().write(vals)
        if meters:
            meters._update_last_reading()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        Meter = self.env['utility.meter']
        Sequence = self.env['ir.sequence']
        sequence_codes = {
            'opening': 'utility.reading.opening',
            'periodic': 'utility.reading.periodic',
            'replacement_closing': 'utility.reading.replacement_closing',
        }
        for vals in vals_list:
            purpose = vals.get('reading_purpose')
            if vals.get('is_initial_reading'):
                purpose = 'opening'
            purpose = purpose or 'periodic'
            vals['reading_purpose'] = purpose
            if vals.get('reading_id', _('جديد')) == _('جديد'):
                sequence_code = sequence_codes.get(purpose, 'utility.reading.periodic')
                vals['reading_id'] = (
                    Sequence.next_by_code(sequence_code)
                    or Sequence.next_by_code('utility.reading')
                    or _('جديد')
                )
            meter = Meter.browse(vals.get('meter_id')).exists() if vals.get('meter_id') else Meter
            if meter:
                vals.setdefault('account_id', meter.customer_id.id)
                vals.setdefault('meter_multiplier', meter.multiplier or 1.0)
            if purpose == 'periodic' and not vals.get('date_range_id'):
                account = self.env['utility.customer'].browse(vals.get('account_id')).exists() if vals.get('account_id') else (meter.customer_id if meter else False)
                billing_period = account._get_effective_billing_period() if account else False
                period_domain = self._get_open_period_domain(
                    work_type='readings', billing_period=billing_period)
                open_period = self.env['date.range'].search(period_domain, limit=1)
                if not open_period:
                    raise ValidationError(_(
                        'لا توجد فترة قراءة مفعلة تطابق دورية المشترك.'))
                vals['date_range_id'] = open_period.id
        records = super().create(vals_list)
        for r in records:
            if r.meter_id:
                r.meter_id._update_last_reading()
        return records
