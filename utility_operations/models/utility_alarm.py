from odoo import api, fields, models, _


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
        ('low_credit', 'رصيد منخفض'),
        ('zero_credit', 'رصيد صفر'),
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
        self.state = 'acknowledged'

    def action_start(self):
        self.state = 'investigating'

    def action_resolve(self):
        self.state = 'resolved'
        self.resolution_date = fields.Datetime.now()

    def action_close(self):
        self.state = 'dismissed'

    def action_create_service_order(self):
        self.ensure_one()
        order = self.env['utility.service.order'].create({
            'service_type': 'tamper_investigation' if self.alarm_type == 'tamper' else 'maintenance',
            'description': self.description,
            'customer_id': self.customer_id.id,
            'account_id': self.account_id.id,
            'meter_id': self.meter_id.id,
            'priority': 'urgent' if self.severity in ('critical', 'emergency') else 'high',
        })
        self.service_order_id = order.id

        if self.alarm_type == 'tamper' and not self.tamper_case_id:
            case = self.env['utility.tamper.case'].create({
                'customer_id': self.customer_id.id,
                'meter_id': self.meter_id.id,
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

    @api.model
    def cron_check_low_credit(self):
        accounts = self.env['utility.customer'].search([('balance', '<', 50.0)])
        for account in accounts:
            existing = self.search([
                ('account_id', '=', account.id),
                ('alarm_type', '=', 'low_credit'),
                ('state', 'not in', ('resolved', 'closed')),
            ], limit=1)
            if existing:
                continue
            self.create({
                'alarm_type': 'low_credit',
                'severity': 'critical' if account.prepaid_balance == 0 else 'warning',
                'description': _('الحساب %s لديه رصيد منخفض: %s') % (account.customer_number, account.prepaid_balance),
                'customer_id': account.id,
                'account_id': account.id,
                'meter_id': account.meter_id.id,
                'region_id': account.region_id.id,
                'area_id': account.area_id.id,
            })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('alarm_code', _('جديد')) == _('جديد'):
                vals['alarm_code'] = self.env['ir.sequence'].next_by_code('utility.alarm') or _('جديد')
        return super().create(vals_list)
