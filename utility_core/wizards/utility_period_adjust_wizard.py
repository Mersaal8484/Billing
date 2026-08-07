from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityPeriodAdjustWizard(models.TransientModel):
    _name = 'utility.period.adjust.wizard'
    _description = 'معالج التعديل المنضبط للفترات والدورات'

    period_id = fields.Many2one(
        'date.range',
        string="الفترة الزمنية",
        required=True,
        ondelete='cascade'
    )
    period_role = fields.Selection(related='period_id.period_role', readonly=True)
    state = fields.Selection(related='period_id.state', readonly=True)

    operation_type = fields.Selection([
        ('extend_reading_window', 'تمديد نافذة القراءة والرفع'),
        ('extend_payment_window', 'تمديد نافذة التحصيل والسداد'),
        ('change_reading_window', 'تعديل نافذة القراءة بأسرها'),
        ('change_consumption_bounds', 'تعديل تواريخ فترة الاستهلاك'),
        ('reopen_period', 'إعادة فتح الفترة الاستثنائي'),
    ], string="نوع العملية المُراد تنفيذها", required=True, default='extend_reading_window')

    current_reading_window_start = fields.Datetime(related='period_id.reading_window_start', readonly=True)
    current_reading_window_end = fields.Datetime(related='period_id.reading_window_end', readonly=True)
    current_payment_window_start = fields.Datetime(related='period_id.payment_window_start', readonly=True)
    current_payment_window_end = fields.Datetime(related='period_id.payment_window_end', readonly=True)
    current_consumption_start = fields.Date(related='period_id.consumption_start', readonly=True)
    current_consumption_end = fields.Date(related='period_id.consumption_end', readonly=True)

    new_reading_window_start = fields.Datetime(string="تاريخ بداية نافذة القراءة الجديد")
    new_reading_window_end = fields.Datetime(string="تاريخ نهاية نافذة القراءة الجديد")
    new_payment_window_start = fields.Datetime(string="تاريخ بداية نافذة التحصيل الجديد")
    new_payment_window_end = fields.Datetime(string="تاريخ نهاية نافذة التحصيل الجديد")
    new_consumption_start = fields.Date(string="تاريخ بداية الاستهلاك الجديد")
    new_consumption_end = fields.Date(string="تاريخ نهاية الاستهلاك الجديد")

    reason = fields.Text(
        string="سبب التعديل والبيان التوثيقي",
        required=True,
        help="يجب تدوين بيان صريح موضح لسبب التعديل ليتم تسجيله في سجل تدقيق الفترة (date.range.log)"
    )

    @api.onchange('period_id', 'operation_type')
    def _onchange_period_defaults(self):
        if not self.period_id:
            return
        p = self.period_id
        self.new_reading_window_start = p.reading_window_start
        self.new_reading_window_end = p.reading_window_end
        self.new_payment_window_start = p.payment_window_start
        self.new_payment_window_end = p.payment_window_end
        self.new_consumption_start = p.consumption_start
        self.new_consumption_end = p.consumption_end

    def action_apply_adjustment(self):
        self.ensure_one()
        p = self.period_id
        if not p:
            raise ValidationError(_("يجب تحديد الفترة الزمنية."))

        if p.state == 'locked':
            raise ValidationError(_("الفترة مقفلة تاريخياً (locked) ولا يمكن تعديلها إطلاقاً."))

        old_vals = {}
        new_vals = {}
        changed_fields_list = []
        write_vals = {}

        if self.operation_type == 'extend_reading_window':
            if not self.new_reading_window_end:
                raise ValidationError(_("يجب تحديد تاريخ نهاية نافذة القراءة الجديد."))
            if self.new_reading_window_end <= p.reading_window_end:
                raise ValidationError(_("التاريخ الجديد ينبغي أن يكون لاحقاً للتاريخ الحالي لتمديد النافذة."))
            
            old_vals['reading_window_end'] = str(p.reading_window_end)
            new_vals['reading_window_end'] = str(self.new_reading_window_end)
            changed_fields_list.append('reading_window_end')
            write_vals['reading_window_end'] = self.new_reading_window_end

        elif self.operation_type == 'extend_payment_window':
            if not self.new_payment_window_end:
                raise ValidationError(_("يجب تحديد تاريخ نهاية نافذة التحصيل الجديد."))
            if self.new_payment_window_end <= p.payment_window_end:
                raise ValidationError(_("التاريخ الجديد ينبغي أن يكون لاحقاً للتاريخ الحالي لتمديد النافذة."))

            old_vals['payment_window_end'] = str(p.payment_window_end)
            new_vals['payment_window_end'] = str(self.new_payment_window_end)
            changed_fields_list.append('payment_window_end')
            write_vals['payment_window_end'] = self.new_payment_window_end

        elif self.operation_type == 'change_reading_window':
            if not self.new_reading_window_start or not self.new_reading_window_end:
                raise ValidationError(_("يجب تحديد بداية ونهاية نافذة القراءة."))
            if self.new_reading_window_start >= self.new_reading_window_end:
                raise ValidationError(_("تاريخ بداية النافذة يجب أن يكون قبل نهايتها."))

            # التأكد من الأثر الجاري
            readings = self.env['utility.reading'].search([('date_range_id', '=', p.id)], limit=1)
            if readings and p.state in ('closing', 'closed'):
                raise ValidationError(_("لا يمكن تعديل نافذة القراءة بفترة في حالة إغلاق تحتوي على قراءات مسجلة."))

            old_vals['reading_window_start'] = str(p.reading_window_start)
            old_vals['reading_window_end'] = str(p.reading_window_end)
            new_vals['reading_window_start'] = str(self.new_reading_window_start)
            new_vals['reading_window_end'] = str(self.new_reading_window_end)
            changed_fields_list.extend(['reading_window_start', 'reading_window_end'])
            write_vals.update({
                'reading_window_start': self.new_reading_window_start,
                'reading_window_end': self.new_reading_window_end,
            })

        elif self.operation_type == 'change_consumption_bounds':
            if not self.new_consumption_start or not self.new_consumption_end:
                raise ValidationError(_("يجب تحديد تواريخ بداية ونهاية الاستهلاك."))
            if self.new_consumption_start >= self.new_consumption_end:
                raise ValidationError(_("تاريخ بداية الاستهلاك يجب أن يكون قبل تاريخ نهايته."))

            # التحقق من وجود فواتير مرتبطة
            orders = self.env['sale.order'].search([('date_range_id', '=', p.id), ('state', '!=', 'cancel')], limit=1)
            if orders:
                raise ValidationError(_("لا يمكن تعديل حد فترات الاستهلاك لوجود فواتير كهرباء منشأة على هذه الفترة."))

            old_vals['consumption_start'] = str(p.consumption_start)
            old_vals['consumption_end'] = str(p.consumption_end)
            new_vals['consumption_start'] = str(self.new_consumption_start)
            new_vals['consumption_end'] = str(self.new_consumption_end)
            changed_fields_list.extend(['consumption_start', 'consumption_end', 'date_start', 'date_end'])
            write_vals.update({
                'consumption_start': self.new_consumption_start,
                'consumption_end': self.new_consumption_end,
                'date_start': self.new_consumption_start,
                'date_end': self.new_consumption_end,
            })

        elif self.operation_type == 'reopen_period':
            p.action_reopen_period(reason=self.reason)
            return {'type': 'ir.actions.act_window_close'}

        if write_vals:
            p.with_context(_bypass_period_scope_protection=True).write(write_vals)
            self.env['date.range.log'].sudo().create({
                'period_id': p.id,
                'old_state': p.state,
                'new_state': p.state,
                'user_id': self.env.uid,
                'timestamp': fields.Datetime.now(),
                'reason': self.reason,
                'action_type': self.operation_type,
                'changed_fields': ", ".join(changed_fields_list),
                'old_values': str(old_vals),
                'new_values': str(new_vals),
            })

        return {'type': 'ir.actions.act_window_close'}
