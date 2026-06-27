from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityReading(models.Model):
    _name = 'utility.reading'
    _description = 'Utility Meter Reading'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reading_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    reading_id = fields.Char('Reading ID', default=lambda self: _('New'), readonly=True)
    
    # --- العداد والحساب ---
    meter_id = fields.Many2one('utility.meter', 'Meter', required=True, index=True)
    customer_id = fields.Many2one('utility.customer', 'Customer/Contract', related='meter_id.customer_id', store=True, index=True)
    account_id = fields.Many2one('utility.customer', 'Account', related='customer_id', store=True)
    
    # --- القراءة ---
    reading_date = fields.Datetime('Reading Date', default=fields.Datetime.now, required=True)
    reading_value = fields.Float('Reading Value', required=True)
    consumption = fields.Float('Consumption', compute='_compute_consumption', store=True)
    reading_type = fields.Selection([
        ('manual', 'يدوي'),
        ('estimated', 'تقديري'),
        ('ami', 'AMI'),
    ], string='Reading Type', default='manual')
    is_estimated = fields.Boolean('تقديرية', default=False)
    
    # --- صور العداد ---
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
    
    # --- المراجعة ---
    reviewer_id = fields.Many2one('res.users', 'المراجع',
        readonly=True, tracking=True)
    review_date = fields.Datetime('تاريخ المراجعة', readonly=True)
    review_notes = fields.Text('ملاحظات المراجعة')
    rejection_reason = fields.Text('سبب الرفض')
    
    is_validated = fields.Boolean('Is Validated', default=False)
    validator_id = fields.Many2one('res.users', 'Validator')
    
    # --- القراءة السابقة (للمقارنة) ---
    previous_reading = fields.Float('القراءة السابقة')
    previous_reading_date = fields.Datetime('تاريخ القراءة السابقة')
    
    # --- تحليل الاستهلاك (للمساعدة في المراجعة) ---
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
    
    # --- الحالة (التدفق الجديد) ---
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('under_review', 'قيد المراجعة'),
        ('approved', 'معتمدة'),
        ('billed', 'مفوترة'),
        ('error', 'خطأ'),
    ], string='الحالة', default='draft', tracking=True)
    
    remarks = fields.Text('ملاحظات')
    reading_source = fields.Char('مصدر القراءة')

    _sql_constraints = [
        ('unique_meter_reading_date',
         'unique(meter_id, reading_date)',
         'يوجد قراءة لنفس العداد في نفس التاريخ!'),
    ]

    # =======================
    #  الحقول المحسوبة
    # =======================

    @api.depends('reading_value', 'previous_reading')
    def _compute_consumption(self):
        for r in self:
            r.consumption = r.reading_value - r.previous_reading if r.previous_reading else 0.0

    @api.depends('consumption', 'meter_id')
    def _compute_consumption_analysis(self):
        for r in self:
            if r.consumption <= 0:
                r.consumption_alert = 'zero' if r.consumption == 0 else 'negative'
                r.consumption_difference = 0
                r.consumption_diff_percentage = 0
                continue
            
            # مقارنة مع آخر قراءة معتمدة
            last_approved = self.search([
                ('meter_id', '=', r.meter_id.id),
                ('state', '=', 'approved'),
                ('id', '!=', r.id),
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

    # =======================
    #  دورة الحياة - الإجراءات
    # =======================

    def action_submit_review(self):
        """إرسال القراءة إلى المراجعة"""
        for r in self:
            if r.state != 'draft':
                raise ValidationError('يمكن إرسال القراءات المسودة فقط للمراجعة!')
            if not r.meter_image:
                raise ValidationError('يجب رفع صورة العداد قبل إرسال القراءة للمراجعة!')
            r.write({
                'state': 'under_review',
                'reading_source': r.reading_source or f'manual_{fields.Datetime.now()}',
            })

    def action_approve(self):
        """الموافقة على القراءة"""
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
        """رفض القراءة وإعادتها للمسودة"""
        for r in self:
            if r.state not in ('under_review', 'approved'):
                raise ValidationError('يمكن رفض القراءات قيد المراجعة أو المعتمدة فقط!')
            r.write({
                'state': 'draft',
                'rejection_reason': r.rejection_reason or 'مرفوضة من قبل المراجع',
            })

    def action_generate_bill(self):
        """إنشاء فاتورة من القراءة المعتمدة"""
        self.ensure_one()
        if self.state != 'approved':
            raise ValidationError('يجب الموافقة على القراءة أولاً قبل إنشاء الفاتورة!')
        if self.state == 'billed':
            raise ValidationError('تم إنشاء فاتورة لهذه القراءة مسبقاً!')
        
        tariff = self.account_id.tariff_id
        consumption = self.consumption
        
        bill_vals = {
            'customer_id': self.customer_id.id,
            'account_id': self.account_id.id,
            'meter_id': self.meter_id.id,
            'bill_date': fields.Date.today(),
            'period_start': self.previous_reading_date.date() if self.previous_reading_date else fields.Date.today(),
            'period_end': self.reading_date.date() if self.reading_date else fields.Date.today(),
            'due_date': fields.Date.today() + timedelta(days=30),
            'previous_reading': self.previous_reading,
            'current_reading': self.reading_value,
            'consumption': consumption,
            'tariff_id': tariff.id if tariff else False,
            'state': 'draft',
        }
        bill = self.env['utility.bill'].create(bill_vals)
        
        # حساب بنود الفاتورة حسب التعرفة
        if tariff:
            bill._calculate_amounts()
        
        self.state = 'billed'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'utility.bill',
            'res_id': bill.id,
            'views': [(False, 'form')],
        }

    # =======================
    #  أوامر Batch
    # =======================

    def action_approve_batch(self):
        """موافقة جماعية على قراءات متعددة"""
        readings = self.filtered(lambda r: r.state == 'under_review')
        readings.action_approve()

    def action_generate_bills_batch(self):
        """إنشاء فواتير لقراءات معتمدة"""
        readings = self.filtered(lambda r: r.state == 'approved')
        for reading in readings:
            reading.action_generate_bill()

    # =======================
    #  التسلسل
    # =======================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reading_id', _('New')) == _('New'):
                vals['reading_id'] = self.env['ir.sequence'].next_by_code('utility.reading') or _('New')
        return super().create(vals_list)
