from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UtilityAlarm(models.Model):
    _name = 'utility.alarm'
    _description = 'إنذار'
    _rec_name = 'alarm_code'
    _order = 'alarm_date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    alarm_code = fields.Char('رمز الإنذار', required=True, index=True, default=lambda self: _('جديد'))
    alarm_date = fields.Datetime('تاريخ الإنذار', default=fields.Datetime.now)
    alarm_type = fields.Selection([
        ('tamper', 'تلاعب'),
        ('power_failure', 'انقطاع التيار'),
        ('comm_failure', 'فشل الاتصال'),
        ('battery', 'بطارية منخفضة'),
        ('reverse_energy', 'طاقة عكسية'),
        ('magnetic', 'تلاعب مغناطيسي'),
        ('over_voltage', 'جهد زائد'),
        ('under_voltage', 'جهد منخفض'),
        ('over_current', 'تيار زائد'),
        ('phase_failure', 'فشل طور'),
        ('other', 'أخرى'),
    ], string='نوع الإنذار', required=True)
    severity = fields.Selection([
        ('info', 'معلومات'),
        ('warning', 'تحذير'),
        ('critical', 'حرج'),
        ('emergency', 'طوارئ'),
    ], string='الخطورة', default='warning')
    customer_id = fields.Many2one('utility.customer', 'العميل')
    account_id = fields.Many2one('utility.customer', 'الحساب', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'العداد')
    area_id = fields.Many2one('utility.region', 'المنطقة الفرعية', domain="[('type', '=', 'area')]")
    region_id = fields.Many2one('utility.region', 'المنطقة', related='area_id.parent_id', store=True)
    description = fields.Text('الوصف', required=True)
    meter_reading = fields.Float('قراءة العداد')
    voltage = fields.Float('الجهد (فولت)')
    current = fields.Float('شدة التيار (أمبير)')
    power = fields.Float('القدرة (كيلوواط)')
    state = fields.Selection([
        ('open', 'مفتوح'),
        ('acknowledged', 'مُسلّم به'),
        ('investigating', 'قيد التحقيق'),
        ('resolved', 'مُحلّى'),
        ('dismissed', 'مرفوض'),
    ], string='الحالة', default='open')
    assigned_to = fields.Many2one('res.users', 'مُعيّن لـ')
    resolution = fields.Text('الحل')
    resolution_date = fields.Datetime('تاريخ الحل')
    service_order_id = fields.Many2one('utility.service.order', 'أمر الخدمة')
    tamper_case_id = fields.Many2one('utility.tamper.case', 'قضية تلاعب')

    def action_acknowledge(self):
        for rec in self:
            if rec.state != 'open':
                raise UserError(_('يمكن فقط التسليم بالإنذار من حالة المفتوح (مفتوح).'))
            rec.state = 'acknowledged'

    def action_start(self):
        for rec in self:
            if rec.state != 'acknowledged':
                raise UserError(_('يمكن فقط بدء التحقيق بعد التسليم بالإنذار (مُسلّم به).'))
            rec.state = 'investigating'

    def action_resolve(self):
        for rec in self:
            if rec.state != 'investigating':
                raise UserError(_('يمكن فقط حل الإنذار عندما يكون قيد التحقيق.'))
            rec.state = 'resolved'
            rec.resolution_date = fields.Datetime.now()

    def action_close(self):
        for rec in self:
            if rec.state in ('resolved', 'dismissed'):
                raise UserError(_('لا يمكن رفض إنذار تم حله أو رفضه بالفعل.'))
            rec.state = 'dismissed'

    def action_create_service_order(self):
        self.ensure_one()
        # Acquire row-level lock FOR UPDATE on the alarm before re-checking service_order_id & tamper_case_id
        self.env.cr.execute("SELECT id FROM utility_alarm WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset(['service_order_id', 'tamper_case_id'])

        if self.service_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'utility.service.order',
                'res_id': self.service_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        order = self.env['utility.service.order'].create({
            'service_type': 'tamper_investigation' if self.alarm_type == 'tamper' else 'maintenance',
            'description': self.description,
            'customer_id': self.customer_id.id if self.customer_id else False,
            'account_id': self.account_id.id if self.account_id else False,
            'meter_id': self.meter_id.id if self.meter_id else False,
            'priority': 'urgent' if self.severity in ('critical', 'emergency') else 'high',
        })
        self.service_order_id = order.id

        if self.alarm_type == 'tamper' and not self.tamper_case_id:
            case = self.env['utility.tamper.case'].create({
                'customer_id': self.customer_id.id if self.customer_id else False,
                'meter_id': self.meter_id.id if self.meter_id else False,
                'tamper_type': 'other',
                'description': _('تم فتح القضية تلقائياً بناءً على إنذار رقم %s: %s') % (self.alarm_code, self.description),
                'severity': self.severity,
            })
            self.tamper_case_id = case.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'utility.service.order',
            'res_id': order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('alarm_code', _('جديد')) == _('جديد'):
                vals['alarm_code'] = self.env['ir.sequence'].next_by_code('utility.alarm') or _('جديد')
        return super().create(vals_list)
