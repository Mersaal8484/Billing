import base64
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


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
    is_rollover = fields.Boolean('تدوير العداد (Rollover)', default=False, tracking=True,
                                 help='يُحدد إذا تجاوز العداد الحد الأقصى وبدأ الدورة من الصفر مجدداً')
    max_reading_value = fields.Float('الحد الأقصى للعداد وقت التدوير', default=99999.0)
    reading_purpose = fields.Selection([
        ('opening', 'افتتاحية'),
        ('periodic', 'دورية'),
        ('closing', 'ختامية'),
        ('replacement_closing', 'ختامية استبدال (توافقي)'),
    ], string='غرض القراءة', default='periodic', required=True, index=True, tracking=True)
    reading_event = fields.Selection([
        ('normal', 'عادية / دورية'),
        ('installation', 'تركيب عداد جديد'),
        ('replacement', 'استبدال عداد'),
        ('disconnection', 'فصل الخدمة'),
        ('removal', 'إزالة عداد'),
        ('contract_closure', 'إنهاء عقد / اشتراك'),
    ], string='حدث القراءة', default='normal', required=True, index=True, tracking=True)
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
    image_asset_id = fields.Many2one('utility.media.asset', string='Meter Image Asset', ondelete='set null', index=True)
    meter_image = fields.Binary('صورة العداد (توافقي)', compute='_compute_meter_image', inverse='_inverse_meter_image', store=False,
                                help='حقل توافقي غير مخزن — التخزين الأصيل ممركز في image_asset_id')
    meter_image_url = fields.Char('رابط صورة العداد', compute='_compute_meter_image_url', store=False, compute_sudo=True)
    meter_image_secondary = fields.Binary('صورة إضافية', attachment=True)
    image_state = fields.Selection([
        ('clear', 'واضحة'),
        ('not_clear', 'غير واضحة'),
        ('not_same', 'لا تطابق العداد'),
        ('none', 'بدون صورة'),
        ('pending', 'بانتظار مراجعة الصورة'),
        ('replace', 'عداد مركب حديثاً'),
        ('loss_read', 'قراءة مفقودة'),
    ], string='حالة الصورة', default='none',
        help='حالة فحص الصورة من قبل المراجع')
    attachment_id = fields.Many2one('ir.attachment', string='ملف المرفق الرسمي')
    reviewer_id = fields.Many2one('res.users', 'المراجع',
        readonly=True, tracking=True)
    review_date = fields.Datetime('تاريخ المراجعة', readonly=True)
    review_notes = fields.Text('ملاحظات المراجعة')
    rejection_reason = fields.Text('سبب الرفض', tracking=True, copy=False)
    rejected_by = fields.Many2one('res.users', 'المستخدم الرافض', readonly=True, copy=False)
    rejected_at = fields.Datetime('تاريخ الرفض', readonly=True, copy=False)
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
    reading_source = fields.Char('مصدر القراءة')

    @api.onchange('reading_type')
    def _onchange_reading_type(self):
        if self.reading_type == 'estimated':
            self.is_estimated = True
        elif self.reading_type in ('manual', 'ami'):
            self.is_estimated = False

    @api.onchange('is_estimated')
    def _onchange_is_estimated(self):
        if self.is_estimated and self.reading_type != 'estimated':
            self.reading_type = 'estimated'
        elif not self.is_estimated and self.reading_type == 'estimated':
            self.reading_type = 'manual'

    @api.depends('image_asset_id', 'image_asset_id.state', 'attachment_id')
    def _compute_meter_image(self):
        MediaService = self.env['utility.media.service']
        for r in self:
            r.meter_image = False
            if r.image_asset_id and r.image_asset_id.state == 'ready':
                raw = MediaService.sudo().retrieve_media(r.image_asset_id.sudo(), variant='review')
                if raw:
                    r.meter_image = base64.b64encode(raw)
                    continue
            if r.attachment_id and r.attachment_id.datas:
                r.meter_image = r.attachment_id.datas

    @api.depends('image_asset_id', 'image_asset_id.state', 'image_asset_id.review_url', 'attachment_id')
    def _compute_meter_image_url(self):
        for r in self:
            asset = r.image_asset_id.sudo() if r.image_asset_id else False
            attachment = r.attachment_id.sudo() if r.attachment_id else False
            if asset and asset.state == 'ready':
                r.meter_image_url = asset.review_url or asset.thumbnail_url or asset.original_url or ''
            elif attachment:
                r.meter_image_url = f"/web/image/{attachment.id}"
            else:
                r.meter_image_url = ''

    def _inverse_meter_image(self):
        for r in self:
            if not r.meter_image:
                continue
            raw = r.meter_image
            if isinstance(raw, str):
                try:
                    raw = base64.b64decode(raw, validate=True)
                except Exception:
                    pass
            if isinstance(raw, bytes) and raw[:4] in (b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'\xff\xd8\xff\xdb', b'\x89PNG', b'RIFF'):
                pass
            else:
                try:
                    raw_decoded = base64.b64decode(raw, validate=True)
                    if raw_decoded[:4] in (b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'\xff\xd8\xff\xdb', b'\x89PNG', b'RIFF'):
                        raw = raw_decoded
                except Exception:
                    pass
            old_asset = r.image_asset_id
            new_asset = self.env['utility.media.service'].sudo().store_media(
                file_data=raw,
                filename=f"reading_{r.id or 'legacy'}.jpg",
                mimetype='image/jpeg',
                reading_id=r.id if isinstance(r.id, int) else False,
                asset_type='meter_reading'
            )
            if old_asset and old_asset != new_asset:
                new_asset.sudo().write({'revision': (old_asset.revision or 1) + 1})
            r.with_context(_bypass_reading_protection=True).write({
                'image_asset_id': new_asset.id,
                'image_state': 'pending' if r.image_state == 'none' else r.image_state,
            })

    def _requires_billing_review(self):
        """Return whether commercial validation rules apply to the reading.

        Core deliberately returns ``False``.  The billing module overrides this
        hook after it installs its commercial fields and rules.
        """
        self.ensure_one()
        return False

    def init(self):
        """Backfill stable accounts and legacy opening-reading purposes on upgrade."""
        self.env.flush_all()
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS utility_reading_meter_date_idx
            ON utility_reading (meter_id, reading_date DESC)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS utility_reading_review_state_image_date_idx
            ON utility_reading (state, image_state, reading_date DESC, id DESC)
        """)
        self.env.cr.execute("""
            UPDATE utility_reading AS reading
               SET image_state = CASE
                   WHEN reading.state IN ('approved', 'queued', 'billed')
                   THEN 'clear'
                   ELSE 'pending'
               END
              FROM utility_media_asset AS asset
             WHERE reading.image_asset_id = asset.id
               AND reading.image_state = 'none'
               AND asset.state NOT IN ('deleted', 'failed')
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
                meter = self.env['utility.meter'].search(
                    self.env['utility.meter']._scan_domain(self.meter_serial_scan),
                    limit=1)

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

    def action_open_meter_images(self):
        """Open the current reading in a modal image form bound to this record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('صورة العداد'),
            'res_model': 'utility.reading',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('utility_billing.view_utility_reading_images').id, 'form')],
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit', 'create': False, 'edit': True},
        }

    _sql_constraints = [
        ('unique_meter_reading_date',
         'unique(meter_id, reading_date)',
         'يوجد قراءة لنفس العداد في نفس التاريخ!'),
    ]

    STATE_EDITABLE = {
        'draft': {'meter_id', 'reading_date', 'reading_value', 'reading_category',
                  'reading_type', 'reading_purpose', 'reading_event', 'account_id', 'meter_multiplier',
                  'is_estimated', 'is_initial_reading', 'is_rollover', 'max_reading_value',
                  'replacement_id', 'meter_image', 'image_asset_id', 'meter_image_secondary',
                  'image_state', 'rejection_reason', 'remarks', 'date_range_id',
                  'reading_source', 'active', 'is_validated', 'validator_id',
                  'reviewer_id', 'review_date', 'rejected_by', 'rejected_at'},
        'under_review': {'meter_image', 'image_asset_id', 'meter_image_secondary', 'image_state',
                          'review_notes', 'rejection_reason', 'rejected_by', 'rejected_at',
                          'is_validated', 'validator_id', 'reviewer_id', 'review_date', 'remarks', 'active'},
        'approved': {'rejection_reason', 'rejected_by', 'rejected_at', 'active', 'attachment_id',
                     'billing_error', 'remarks'},
        'queued': {'attachment_id', 'billing_error', 'remarks', 'active'},
        'billed': {'active', 'remarks', 'billing_error'},
        'error': {'reading_date', 'reading_value', 'meter_image', 'image_asset_id', 'meter_image_secondary',
                  'is_rollover', 'max_reading_value',
                  'image_state', 'remarks', 'date_range_id', 'billing_error', 'active'},
    }

    @api.constrains('reading_purpose', 'date_range_id', 'replacement_id', 'account_id', 'reading_date')
    def _check_reading_purpose_rules(self):
        """Enforce period, replacement, and billing-anchor invariants."""
        for reading in self:
            if reading.reading_purpose != 'periodic' and reading.date_range_id:
                raise ValidationError(_('الفترة مسموحة للقراءة الدورية فقط.'))
            if reading.reading_purpose == 'replacement_closing' and not reading.replacement_id:
                raise ValidationError(_('القراءة الختامية تتطلب عملية استبدال مرتبطة.'))

    @api.constrains('is_rollover', 'max_reading_value', 'reading_value', 'previous_reading')
    def _check_rollover_integrity(self):
        for r in self:
            if r.is_rollover:
                if r.max_reading_value <= 0:
                    raise ValidationError(_('الحد الأقصى للعداد وقت التدوير يجب أن يكون قيمة موجبة أكبر من الصفر.'))
                if r.reading_value > r.max_reading_value:
                    raise ValidationError(_(
                        'قيمة القراءة الحالية (%.2f) لا يمكن أن تتجاوز الحد الأقصى للعداد (%.2f).'
                    ) % (r.reading_value, r.max_reading_value))
                if (r.previous_reading or 0.0) > r.max_reading_value:
                    raise ValidationError(_(
                        'قيمة القراءة السابقة (%.2f) تتجاوز الحد الأقصى للعداد (%.2f).'
                    ) % (r.previous_reading or 0.0, r.max_reading_value))
                if r.reading_value >= (r.previous_reading or 0.0):
                    raise ValidationError(_(
                        'لا يمكن تفعيل خيار تدوير العداد إذا كانت القراءة الحالية (%.2f) أكبر من أو تساوي القراءة السابقة (%.2f).'
                    ) % (r.reading_value, r.previous_reading or 0.0))
                if r.consumption <= 0:
                    raise ValidationError(_('الاستهلاك المحسوب من تدوير العداد يجب أن يكون أكبر من الصفر.'))

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

    @api.depends('reading_value', 'previous_reading', 'is_initial_reading', 'reading_purpose', 'meter_multiplier', 'is_rollover', 'max_reading_value')
    def _compute_consumption(self):
        for r in self:
            if r.is_initial_reading or r.reading_purpose == 'opening':
                r.raw_consumption = 0.0
                r.consumption = 0.0
            else:
                prev = r.previous_reading or 0.0
                curr = r.reading_value or 0.0
                if r.is_rollover and curr < prev:
                    max_val = r.max_reading_value if r.max_reading_value > 0 else 99999.0
                    raw = (max_val - prev + 1.0) + curr
                else:
                    raw = curr - prev
                r.raw_consumption = raw
                r.consumption = raw * (r.meter_multiplier or 1.0)

    @api.depends('consumption', 'meter_id', 'reading_purpose')
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
            # Opening readings: zero consumption is EXPECTED, never flag
            if r.reading_purpose == 'opening':
                r.consumption_alert = 'normal'
                r.consumption_difference = 0
                r.consumption_diff_percentage = 0
                continue

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

    def _get_effective_previous_reading(self):
        """Return the effective previous reading value for the NEXT reading's consumption calculation.

        The historical ``reading_value`` is preserved immutably forever.
        If a technically-approved (or processed) correction exists for this
        reading, the ``corrected_reading_value`` is used as the operational
        baseline for the subsequent reading — without mutating any stored data.

        This is the canonical resolver used by downstream consumption
        calculations. Never use ``reading_value`` directly when computing
        consumption for the reading that *follows* this one.

        Returns:
            float: The corrected reading value if an approved settlement exists,
                   otherwise the immutable historical reading_value.
        """
        self.ensure_one()
        # Avoid circular import: use model name string, not import
        Settlement = self.env.get('utility.reading.settlement')
        if Settlement is not None:
            approved = Settlement.search([
                ('reading_id', '=', self.id),
                ('state', 'in', ('technically_approved', 'processed')),
            ], limit=1, order='approved_date desc')
            if approved:
                return approved.corrected_reading_value
        return self.reading_value


    def action_submit_review(self):
        for r in self:
            if r.state != 'draft':
                raise ValidationError('يمكن إرسال القراءات المسودة فقط للمراجعة!')

            if not r.meter_image and r._requires_billing_review():
                raise ValidationError('يجب رفع صورة العداد قبل إرسال القراءة للمراجعة!')

            r.with_context(_reading_state_transition=True).write({
                'reading_source': r.reading_source or f'manual_{fields.Datetime.now()}',
                'state': 'under_review',
            })

    def action_approve(self):
        if not (self.env.user.has_group('utility_core.group_utility_supervisor')
                or self.env.user.has_group('utility_core.group_utility_billing_manager')
                or self.env.user.has_group('utility_core.group_utility_revenue_manager')
                or self.env.user.has_group('utility_core.group_utility_admin')
                or self.env.su):
            raise AccessError(_('ليس لديك صلاحية اعتماد قراءات العدادات. يتطلب صلاحية مشرف أو مدير فوترة أو مدير إيرادات.'))

        for r in self:
            if r.state != 'under_review':
                raise ValidationError('يمكن الموافقة على القراءات قيد المراجعة فقط!')

            if r._requires_billing_review() and r.image_state != 'clear':
                raise ValidationError(
                    'لا يمكن اعتماد القراءة قبل اعتماد الصورة كصورة واضحة (clear).'
                )

            # FIX-4: منع اعتماد قراءة باستهلاك سالب للقراءات القابلة للفوترة
            if r._requires_billing_review() and r.consumption < 0:
                raise ValidationError(
                    'لا يمكن اعتماد قراءة باستهلاك سالب (%.2f). '
                    'تحقق من صحة القراءة أو أنشئ تسوية.'
                    % r.consumption
                )

            r.with_context(_reading_state_transition=True).write({
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
        if not (self.env.user.has_group('utility_core.group_utility_supervisor')
                or self.env.user.has_group('utility_core.group_utility_billing_manager')
                or self.env.user.has_group('utility_core.group_utility_revenue_manager')
                or self.env.user.has_group('utility_core.group_utility_admin')
                or self.env.su):
            raise AccessError(_('ليس لديك صلاحية رفض قراءات العدادات. يتطلب صلاحية مشرف أو مدير فوترة أو مدير إيرادات.'))

        for r in self:
            # FIX-1: منع رفض قراءة مفوترة — يجب إلغاء الفاتورة أولاً أو استخدام تسوية
            if r.state == 'billed':
                raise ValidationError(_(
                    'لا يمكن رفض قراءة مفوترة مباشرةً.\n'
                    'قم بإلغاء الفاتورة المرتبطة أولاً، '
                    'أو استخدم نموذج تسوية القراءات لتعديل القيمة.'
                ))
            if r.state not in ('under_review', 'approved'):
                raise ValidationError(_('يمكن رفض القراءات قيد المراجعة أو المعتمدة فقط!'))

            reason = r.rejection_reason or self.env.context.get('default_rejection_reason')
            if not reason or not reason.strip():
                raise ValidationError(_('يجب تحديد سبب رفض القراءة لتوجيه القارئ الميداني للتصحيح.'))

            r.with_context(_reading_state_transition=True).write({
                'state': 'draft',
                'rejection_reason': reason.strip(),
                'rejected_by': self.env.user.id,
                'rejected_at': fields.Datetime.now(),
                'is_validated': False,
                'validator_id': False,
                'reviewer_id': False,
                'review_date': False,
            })
            r.message_post(
                body=_('تم رفض القراءة ونقلها إلى مسودة بواسطة %s. سبب الرفض: %s') % (
                    self.env.user.name,
                    reason.strip()
                )
            )

    def action_approve_batch(self):
        readings = self.filtered(lambda r: r.state == 'under_review')
        readings.action_approve()

    def write(self, vals):
        # Sync reading_type and is_estimated
        if vals.get('reading_type') == 'estimated':
            vals['is_estimated'] = True
        elif vals.get('is_estimated'):
            vals['reading_type'] = 'estimated'
        elif vals.get('reading_type') in ('manual', 'ami') and 'is_estimated' not in vals:
            vals['is_estimated'] = False

        # P0 Guard: state cannot be directly mutated outside controlled transitions
        if 'state' in vals and not (
                self.env.context.get('_reading_state_transition')
                or self.env.context.get('_bypass_reading_protection')
                or self.env.context.get('allow_billing_adjustment')):
            raise ValidationError(_('لا يمكن تغيير حالة القراءة مباشرةً. يجب استخدام أزرار وسير العمل المعتمد.'))

        if not (self.env.context.get('_bypass_reading_protection') or self.env.context.get('allow_billing_adjustment')):
            bypass_fields = {'active', 'remarks', 'rejection_reason', 'rejected_by', 'rejected_at'}
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
            if vals.get('reading_type') == 'estimated':
                vals['is_estimated'] = True
            elif vals.get('is_estimated'):
                vals['reading_type'] = 'estimated'

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
            if r.image_asset_id and r.image_state == 'none':
                r.with_context(_bypass_reading_protection=True).write({
                    'image_state': (
                        'clear' if r.state in ('approved', 'queued', 'billed')
                        else 'pending'
                    ),
                })
            if r.meter_id:
                r.meter_id._update_last_reading()
            if r.image_asset_id and not r.image_asset_id.reading_id:
                r.image_asset_id.sudo().write({'reading_id': r.id})
        return records
