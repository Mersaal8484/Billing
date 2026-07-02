from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityReading(models.Model):
    _name = 'utility.reading'
    _description = 'Utility Meter Reading'
    _rec_name = 'reading_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reading_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    reading_id = fields.Char('Reading ID', default=lambda self: _('New'), readonly=True)
    meter_id = fields.Many2one('utility.meter', 'Meter', required=True, index=True)
    customer_id = fields.Many2one('utility.customer', 'Customer/Contract', related='meter_id.customer_id', store=True, index=True)
    account_id = fields.Many2one('utility.customer', 'Account', related='customer_id', store=True)
    reading_date = fields.Datetime('Reading Date', default=fields.Datetime.now, required=True)
    reading_value = fields.Float('Reading Value', required=True)
    consumption = fields.Float('Consumption', compute='_compute_consumption', store=True)
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
        ('ami', 'AMI'),
    ], string='Reading Type', default='manual')
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
    is_validated = fields.Boolean('Is Validated', default=False)
    validator_id = fields.Many2one('res.users', 'Validator')
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
    ], string='الحالة', default='draft', tracking=True)
    date_range_id = fields.Many2one('date.range', string="الفترة", index=True)
    remarks = fields.Text('ملاحظات')
    billing_error = fields.Text('خطأ الفوترة', readonly=True)
    reading_source = fields.Char('مصدر القراءة')
    batch_id = fields.Many2one('utility.reading.batch', 'الدفعة', readonly=True, index=True)

    _sql_constraints = [
        ('unique_meter_reading_date',
         'unique(meter_id, reading_date)',
         'يوجد قراءة لنفس العداد في نفس التاريخ!'),
    ]

    @api.depends('reading_value', 'previous_reading')
    def _compute_consumption(self):
        for r in self:
            # If previous reading is 0 or False, we still want to calculate consumption 
            # based on current reading, but usually for first reading we might want to be careful.
            # However, `reading_value - previous_reading` handles this correctly (e.g. 150 - 0 = 150).
            r.consumption = r.reading_value - (r.previous_reading or 0.0)

    @api.depends('consumption', 'meter_id')
    def _compute_consumption_analysis(self):
        for r in self:
            if r.consumption <= 0:
                r.consumption_alert = 'zero' if r.consumption == 0 else 'negative'
                r.consumption_difference = 0
                r.consumption_diff_percentage = 0
                continue
            last_approved = self.search([
                ('meter_id', '=', r.meter_id.id),
                ('state', '=', 'approved'),
                ('id', '!=', r._origin.id if r._origin else False),
            ], order='reading_date desc', limit=1)
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
        for r in self:
            prev = self.search([
                ('meter_id', '=', r.meter_id.id),
                ('reading_date', '<', r.reading_date),
                ('state', 'in', ['approved', 'billed']),
            ], order='reading_date desc', limit=1)
            r.previous_reading = prev.reading_value if prev else 0.0
            r.previous_reading_date = prev.reading_date if prev else False

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
            r.write({
                'state': 'approved',
                'is_validated': True,
                'validator_id': self.env.user.id,
                'reviewer_id': self.env.user.id,
                'review_date': fields.Datetime.now(),
            })

    def action_reject(self):
        for r in self:
            if r.state not in ('under_review', 'approved'):
                raise ValidationError('يمكن رفض القراءات قيد المراجعة أو المعتمدة فقط!')
            r.write({
                'state': 'draft',
                'rejection_reason': r.rejection_reason or 'مرفوضة من قبل المراجع',
            })

    def action_generate_bill(self):
        """إنشاء أمر بيع (فاتورة) من القراءة المعتمدة وربط المرفق رسمياً"""
        self.ensure_one()
        is_billable = (self.reading_category == 'customer' or (self.reading_category == 'transformer' and self.is_private_transformer))
        if not is_billable:
            raise ValidationError('إنشاء الفواتير متاح فقط لقراءات المشتركين والمحولات الخاصة!')
        if self.state != 'approved':
            raise ValidationError('يجب الموافقة على القراءة أولاً قبل إنشاء الفاتورة!')
        if self.state == 'billed':
            raise ValidationError('تم إنشاء فاتورة لهذه القراءة مسبقاً!')
        template = self.account_id.contract_template_id
        consumption = self.consumption
        order = self.env['sale.order'].create({
            'partner_id': self.account_id.partner_id.id if self.account_id.partner_id else self.env.company.partner_id.id,
            'customer_id': self.account_id.id,
            'meter_id': self.meter_id.id,
            'reading_id': self.id,
            'date_order': fields.Datetime.now(),
            'period_start': self.previous_reading_date.date() if self.previous_reading_date else fields.Date.today(),
            'period_end': self.reading_date.date() if self.reading_date else fields.Date.today(),
            'previous_reading': self.previous_reading,
            'current_reading': self.reading_value,
            'consumption': consumption,
            'contract_template_id': template.id if template else False,
            'bill_state': 'draft',
        })
        if template:
            order._calculate_amounts()
            
        # إنشاء/نقل ملف المرفق الخاص بصورة العداد مباشرة إلى أمر البيع (الفاتورة)
        if self.meter_image:
            attach = self.env['ir.attachment'].create({
                'name': f'invoice_meter_{order.name or self.reading_id}.png',
                'type': 'binary',
                'datas': self.meter_image,
                'res_model': 'sale.order',
                'res_id': order.id,
            })
            order.attachment_id = attach.id
            self.attachment_id = attach.id

        self.state = 'billed'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': order.id,
            'views': [(False, 'form')],
        }

    def action_approve_batch(self):
        readings = self.filtered(lambda r: r.state == 'under_review')
        readings.action_approve()

    def action_generate_bills_batch(self):
        """Action: تحويل القراءات المعتمدة إلى طابور الفوترة للمعالجة المجدولة"""
        readings = self.filtered(lambda r: r.state == 'approved' and (
            r.reading_category == 'customer' or
            (r.reading_category == 'transformer' and r.is_private_transformer)
        ))
        if not readings:
            raise ValidationError('لا توجد قراءات معتمدة قابلة للفوترة!')
        readings.write({'state': 'queued', 'billing_error': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'طابور الفوترة',
                'message': f'تم إرسال {len(readings)} قراءة إلى طابور الفوترة. سيتم معالجتها تلقائياً.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_requeue(self):
        """إعادة القراءات الفاشلة إلى طابور الفوترة"""
        for r in self:
            if r.state != 'error':
                raise ValidationError('يمكن إعادة المحاولة فقط للقراءات التي بها خطأ!')
            r.write({'state': 'queued', 'billing_error': False})

    @api.model
    def _cron_generate_bills(self):
        """مهمة مجدولة: إنشاء فواتير من القراءات في الطابور على دفعات"""
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'utility.billing_batch_size', 500))
        readings = self.search([('state', '=', 'queued')], limit=batch_size)
        if not readings:
            return

        success_count = 0
        error_count = 0
        for reading in readings:
            try:
                reading.action_generate_bill()
                self.env.cr.commit()
                success_count += 1
            except Exception as e:
                self.env.cr.rollback()
                reading.write({
                    'state': 'error',
                    'billing_error': str(e),
                })
                self.env.cr.commit()
                error_count += 1

        _logger = __import__('logging').getLogger(__name__)
        _logger.info(
            'Batch Billing: processed %d readings (%d success, %d errors)',
            len(readings), success_count, error_count
        )
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reading_id', _('New')) == _('New'):
                vals['reading_id'] = self.env['ir.sequence'].next_by_code('utility.reading') or _('New')
        return super().create(vals_list)
