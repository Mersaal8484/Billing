from odoo import api, fields, models, _


class UtilityMeterLog(models.Model):
    _name = 'utility.meter.log'
    _description = 'سجل تاريخ العداد'
    _order = 'date desc, id desc'
    _rec_name = 'name'

    name = fields.Char('المرجع', compute='_compute_name')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, index=True, ondelete='cascade')
    date = fields.Datetime('التاريخ', default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', 'المستخدم', default=lambda self: self.env.user)

    @api.depends('meter_id', 'log_type', 'date')
    def _compute_name(self):
        for rec in self:
            if rec.meter_id and rec.log_type:
                log_label = dict(self._fields['log_type'].selection).get(rec.log_type, rec.log_type)
                rec.name = f"{log_label} - {rec.meter_id.display_name}"
            else:
                rec.name = "سجل جديد"

    log_type = fields.Selection([
        ('installation', 'تركيب'),
        ('replacement', 'استبدال'),
        ('removal', 'رفع'),
        ('settlement', 'تسوية قراءة'),
        ('service_order', 'أمر خدمة'),
        ('disconnection', 'فصل'),
        ('reconnection', 'إعادة خدمة'),
        ('movement', 'حركة مخزون'),
        ('status_change', 'Status Change'),
        ('transfer', 'Customer Transfer'),
        ('reading', 'قراءة'),
        ('other', 'أخرى'),
    ], string='نوع الحدث', required=True)

    description = fields.Text('الوصف', required=True)
    ref_model = fields.Char('النموذج المصدر')
    ref_id = fields.Integer('معرف السجل المصدر')
    ref_name = fields.Char('المرجع')
    customer_id = fields.Many2one('utility.customer', 'الحساب/العميل وقت الحدث')

    def _create_log(self, meter_id, log_type, description, ref_record=None, date=None, customer_id=None):
        vals = {
            'meter_id': meter_id.id if hasattr(meter_id, 'id') else meter_id,
            'log_type': log_type,
            'description': description,
            'date': date or fields.Datetime.now(),
        }
        if customer_id:
            vals['customer_id'] = customer_id.id if hasattr(customer_id, 'id') else customer_id

        if ref_record:
            vals.update({
                'ref_model': ref_record._name,
                'ref_id': ref_record.id,
                'ref_name': ref_record.display_name if hasattr(ref_record, 'display_name') else str(ref_record),
            })
        return self.create(vals)

    def write(self, vals):
        if not self.env.context.get('allow_log_update'):
            from odoo.exceptions import UserError
            raise UserError('أمان النظام: لا يُسمح بتعديل سجلات العدادات التاريخية لضمان موثوقية التدقيق.')
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get('allow_log_update'):
            from odoo.exceptions import UserError
            raise UserError('أمان النظام: لا يُسمح بحذف سجلات العدادات التاريخية لضمان موثوقية التدقيق.')
        return super().unlink()
