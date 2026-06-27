from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityReadingSettlement(models.Model):
    _name = 'utility.reading.settlement'
    _description = 'Reading Settlement Logs'
    _order = 'adjustment_date desc'

    name = fields.Char('رقم التسوية', default=lambda self: _('New'), readonly=True)
    reading_id = fields.Many2one('utility.reading', 'القراءة المستهدفة', required=True)
    meter_id = fields.Many2one('utility.meter', related='reading_id.meter_id', store=True)
    account_id = fields.Many2one('utility.customer', related='reading_id.account_id', store=True)
    
    old_value = fields.Float('القراءة القديمة', readonly=True)
    new_value = fields.Float('القراءة الجديدة المعدلة', required=True)
    
    adjusted_by = fields.Many2one('res.users', 'تمت التسوية بواسطة', default=lambda self: self.env.user, readonly=True)
    adjustment_date = fields.Date('تاريخ التسوية', default=fields.Date.today, readonly=True)
    reason = fields.Text('سبب التعديل والتسوية', required=True)
    
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('done', 'تمت التسوية'),
    ], string='الحالة', default='draft', readonly=True)

    @api.onchange('reading_id')
    def _onchange_reading_id(self):
        if self.reading_id:
            self.old_value = self.reading_id.reading_value

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.reading.settlement') or _('New')
        return super().create(vals_list)

    def action_apply_settlement(self):
        self.ensure_one()
        if self.state == 'done':
            raise ValidationError('هذه التسوية مكتملة بالفعل!')
        
        # حفظ القيمة القديمة للتأكيد
        self.old_value = self.reading_id.reading_value
        
        # 1. تحديث القيمة في القراءة وإعادة حساب الاستهلاك
        self.reading_id.write({
            'reading_value': self.new_value,
        })
        self.reading_id._compute_consumption()
        
        # 2. إعادة حساب الاستهلاك والفاقد في القراءات التالية إن وجدت
        self.state = 'done'
        return True
