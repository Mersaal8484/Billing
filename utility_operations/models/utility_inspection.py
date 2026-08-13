from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UtilityInspection(models.Model):
    _name = 'utility.inspection'
    _description = 'معاينة'
    _rec_name = 'name'
    _order = 'inspection_date desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('رقم المعاينة', required=True, index=True, default=lambda self: _('جديد'))
    service_order_id = fields.Many2one('utility.service.order', 'أمر الخدمة')
    customer_id = fields.Many2one('utility.customer', 'العميل')
    account_id = fields.Many2one('utility.customer', 'الحساب', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'العداد')
    inspection_type = fields.Selection([
        ('pre_installation', 'قبل التركيب'),
        ('post_installation', 'بعد التركيب'),
        ('routine', 'روتينية'),
        ('tamper', 'تلاعب'),
        ('safety', 'سلامة'),
        ('theft', 'سرقة'),
    ], string='نوع المعاينة', required=True)
    inspector_id = fields.Many2one('res.users', 'المُفتّش')
    inspection_date = fields.Datetime('تاريخ المعاينة', default=fields.Datetime.now)
    findings = fields.Text('الملاحظات')
    condition_rating = fields.Integer('تقييم الحالة (1-5)')
    address = fields.Text('العنوان')
    customer_signature = fields.Binary('توقيع العميل')
    inspector_signature = fields.Binary('توقيع المُفتّش')
    is_passed = fields.Boolean('ناجحة')
    notes = fields.Text('ملاحظات')
    state = fields.Selection([
        ('scheduled', 'مجدولة'),
        ('completed', 'مكتملة'),
        ('cancelled', 'ملغاة'),
    ], string='الحالة', default='scheduled')

    @api.constrains('condition_rating')
    def _check_condition_rating(self):
        for rec in self:
            if rec.condition_rating and not (1 <= rec.condition_rating <= 5):
                raise ValidationError(_('تقييم الحالة يجب أن يكون بين 1 و 5.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('جديد')) == _('جديد'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.inspection') or _('جديد')
        return super().create(vals_list)

    def action_complete(self):
        for rec in self:
            if rec.state != 'scheduled':
                raise UserError(_('لا يمكن إكمال المعاينة إلا عندما تكون مجدولة.'))
            if not rec.inspection_type:
                raise ValidationError(_('نوع المعاينة مطلوب لإتمام المعاينة.'))
            if not rec.inspector_id:
                raise ValidationError(_('اسم المُفتّش مطلوب لإتمام المعاينة.'))
            if not rec.inspection_date:
                rec.inspection_date = fields.Datetime.now()
            if rec.condition_rating and not (1 <= rec.condition_rating <= 5):
                raise ValidationError(_('تقييم الحالة يجب أن يكون بين 1 و 5.'))
            rec.state = 'completed'

    def action_cancel(self):
        for rec in self:
            if rec.state != 'scheduled':
                raise UserError(_('لا يمكن إلغاء المعاينة إلا عندما تكون مجدولة.'))
            rec.state = 'cancelled'

