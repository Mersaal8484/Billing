from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMeterReplacement(models.Model):
    _inherit = 'utility.meter.replacement'
    _description = 'سجل استبدال العداد'
    _order = 'replacement_date desc'

    order_number = fields.Char('رقم العملية', default=lambda self: _('New'), readonly=True)
    replacement_date = fields.Date('تاريخ الاستبدال', default=fields.Date.today, required=True)
    old_meter_final_reading = fields.Float('القراءة النهائية للقديم', required=True)
    new_meter_initial_reading = fields.Float('القراءة الابتدائية للجديد', default=0.0, required=True)
    unbilled_consumption = fields.Float('الاستهلاك غير المفوتر للقديم', compute='_compute_unbilled_consumption', store=True)
    replacement_notes = fields.Text('ملاحظات الاستبدال')

    @api.depends('old_meter_final_reading', 'utility_account_id.last_invoice_reading')
    def _compute_unbilled_consumption(self):
        for rec in self:
            last_invoiced = rec.utility_account_id.last_invoice_reading or 0.0
            rec.unbilled_consumption = max(0.0, rec.old_meter_final_reading - last_invoiced)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('order_number', _('New')) == _('New'):
                vals['order_number'] = self.env['ir.sequence'].next_by_code('utility.meter.replacement') or _('New')
        return super().create(vals_list)

    def action_complete_replacement(self):
        self.ensure_one()
        if self.state == 'done':
            raise ValidationError('هذه العملية مكتملة بالفعل!')
        
        acc = self.utility_account_id
        old_meter = self.old_meter_id
        new_meter = self.new_meter_id
        
        if not acc:
            raise ValidationError('يجب تحديد حساب الكهرباء!')
        if not old_meter:
            raise ValidationError('يجب تحديد العداد القديم!')
        if not new_meter:
            raise ValidationError('يجب تحديد العداد الجديد!')
        
        # 1. تحديث العداد في الحساب
        acc.write({
            'meter_id': new_meter.id,
            'last_reading_value': self.new_meter_initial_reading,
            'last_invoice_reading': self.new_meter_initial_reading,
        })
        
        # 2. إيقاف العداد القديم وتعديل حالة الجديد
        old_meter.write({
            'active': False,
            'customer_id': False,
        })
        new_meter.write({
            'customer_id': acc.id,
            'last_read_date': fields.Datetime.now(),
        })
        
        # 3. تسجيل قراءة نهائية للقديم وقراءة ابتدائية للجديد
        Reading = self.env['utility.reading']
        
        Reading.create({
            'meter_id': old_meter.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': self.old_meter_final_reading,
            'reading_type': 'manual',
            'reading_category': 'customer',
            'state': 'approved',
            'remarks': f'قراءة إغلاق نهائية بسبب استبدال العداد بالعملية {self.order_number or self.name}',
        })
        
        Reading.create({
            'meter_id': new_meter.id,
            'reading_date': fields.Datetime.now(),
            'reading_value': self.new_meter_initial_reading,
            'reading_type': 'manual',
            'reading_category': 'customer',
            'state': 'approved',
            'remarks': f'قراءة افتتاحية ابتدائية بسبب استبدال العداد بالعملية {self.order_number or self.name}',
        })
        
        self.state = 'done'
        return True
