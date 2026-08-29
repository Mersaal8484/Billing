from odoo import api, fields, models, _


class UtilityReadingBatchLine(models.Model):
    _name = 'utility.reading.batch.line'
    _description = 'سطر تفصيلي لدفعة قراءات العدادات'
    _order = 'seq asc, id asc'

    batch_id = fields.Many2one('utility.reading.batch', string='الدفعة المرتبطة', required=True, ondelete='cascade', index=True)
    seq = fields.Integer('تسلسل', default=1)
    meter_id = fields.Many2one('utility.meter', string='العداد', index=True, ondelete='set null')
    resubmit_reading_id = fields.Many2one(
        'utility.reading', string='القراءة المعادة للمراجعة', index=True,
        ondelete='set null',
        help='لا يُستخدم إلا لتحديث قراءة أعادها المراجع إلى المسودة.',
    )
    meter_number = fields.Char('رقم العداد', required=True, index=True)
    reading_value = fields.Float('قيمة القراءة', required=True)
    reading_date = fields.Datetime('تاريخ القراءة', default=fields.Datetime.now)
    reading_category = fields.Selection([
        ('customer', 'مشترك'),
        ('transformer', 'محول'),
        ('feeder', 'فيدر'),
        ('cell', 'خلية'),
    ], string='تصنيف القراءة', default='customer')
    image_filename = fields.Char('اسم ملف الصورة')
    reading_id = fields.Many2one('utility.reading', string='القراءة المُنشأة', ondelete='set null')

    state = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('processing', 'قيد المعالجة'),
        ('done', 'تم بنجاح'),
        ('failed', 'فشلت'),
    ], string='حالة السطر', default='pending', required=True, index=True)

    error_message = fields.Text('رسالة الخطأ')
