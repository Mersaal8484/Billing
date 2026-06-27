from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMeterReplacement(models.Model):
    _name = 'utility.meter.replacement'
    _description = 'Meter Replacement History'
    _order = 'replacement_date desc'

    name = fields.Char('رقم العملية', default=lambda self: _('New'), readonly=True)
    account_id = fields.Many2one('utility.customer', 'حساب الكهرباء', required=True)
    customer_id = fields.Many2one('utility.customer', related='account_id', store=True)
    old_meter_id = fields.Many2one('utility.meter', 'العداد القديم', required=True)
    new_meter_id = fields.Many2one('utility.meter', 'العداد الجديد', required=True)
    replacement_date = fields.Date('تاريخ الاستبدال', default=fields.Date.today, required=True)
    
    old_meter_final_reading = fields.Float('القراءة النهائية للقديم', required=True)
    new_meter_initial_reading = fields.Float('القراءة الابتدائية للجديد', default=0.0, required=True)
    unbilled_consumption = fields.Float('الاستهلاك غير المفوتر للقديم', compute='_compute_unbilled_consumption', store=True)
    
    reason = fields.Text('سبب الاستبدال')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('done', 'تم الاستبدال'),
    ], string='الحالة', default='draft', readonly=True)

    @api.depends('old_meter_final_reading', 'account_id.last_invoice_reading')
    def _compute_unbilled_consumption(self):
        for rec in self:
            last_invoiced = rec.account_id.last_invoice_reading or 0.0
            rec.unbilled_consumption = max(0.0, rec.old_meter_final_reading - last_invoiced)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.meter.replacement') or _('New')
        return super().create(vals_list)

    def action_complete_replacement(self):
        self.ensure_one()
        if self.state == 'done':
            raise ValidationError('هذه العملية مكتملة بالفعل!')
        
        # 1. تحديث العداد في الحساب
        self.account_id.write({
            'meter_id': self.new_meter_id.id,
            'last_reading_value': self.new_meter_initial_reading,
            'last_invoice_reading': self.new_meter_initial_reading,
        })
        
        # 2. إيقاف العداد القديم وتعديل حالة الجديد
        self.old_meter_id.write({
            'active': False,
            'account_id': False,
        })
        self.new_meter_id.write({
            'account_id': self.account_id.id,
            'last_read_date': fields.Datetime.now(),
        })
        
        # 3. تسجيل قراءة نهائية للقديم وقراءة ابتدائية للجديد
        Reading = self.env['utility.reading']
        
        # قراءة إغلاق العداد القديم
        Reading.create({
            'meter_id': self.old_meter_id.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': self.old_meter_final_reading,
            'reading_type': 'manual',
            'state': 'approved',
            'remarks': f'قراءة إغلاق نهائية بسبب استبدال العداد بالعملية {self.name}',
        })
        
        # قراءة فتح العداد الجديد
        Reading.create({
            'meter_id': self.new_meter_id.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': self.new_meter_initial_reading,
            'reading_type': 'manual',
            'state': 'approved',
            'remarks': f'قراءة افتتاحية ابتدائية بسبب استبدال العداد بالعملية {self.name}',
        })
        
        self.state = 'done'
        return True
