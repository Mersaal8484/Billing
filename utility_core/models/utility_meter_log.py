from odoo import api, fields, models, _


class UtilityMeterLog(models.Model):
    _name = 'utility.meter.log'
    _description = 'سجل تاريخ العداد'
    _order = 'date desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, index=True, ondelete='cascade')
    date = fields.Datetime('التاريخ', default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', 'المستخدم', default=lambda self: self.env.user)

    log_type = fields.Selection([
        ('installation', 'تركيب'),
        ('replacement', 'استبدال'),
        ('removal', 'رفع'),
        ('settlement', 'تسوية قراءة'),
        ('service_order', 'أمر خدمة'),
        ('disconnection', 'فصل'),
        ('reconnection', 'إعادة خدمة'),
        ('movement', 'حركة مخزون'),
        ('reading', 'قراءة'),
        ('other', 'أخرى'),
    ], string='نوع الحدث', required=True)

    description = fields.Text('الوصف', required=True)
    ref_model = fields.Char('النموذج المصدر')
    ref_id = fields.Integer('معرف السجل المصدر')
    ref_name = fields.Char('المرجع')

    def _create_log(self, meter_id, log_type, description, ref_record=None, date=None):
        vals = {
            'meter_id': meter_id.id if hasattr(meter_id, 'id') else meter_id,
            'log_type': log_type,
            'description': description,
            'date': date or fields.Datetime.now(),
        }
        if ref_record:
            vals.update({
                'ref_model': ref_record._name,
                'ref_id': ref_record.id,
                'ref_name': ref_record.display_name if hasattr(ref_record, 'display_name') else str(ref_record),
            })
        return self.create(vals)
