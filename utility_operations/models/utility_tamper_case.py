from odoo import api, fields, models, _


class UtilityTamperCase(models.Model):
    _name = 'utility.tamper.case'
    _description = 'حالة تلاعب'
    _rec_name = 'case_number'
    _inherit = ['mail.thread']
    _order = 'date_reported desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    case_number = fields.Char('رقم الحالة', required=True, index=True, default=lambda self: _('جديد'))
    date_reported = fields.Datetime('تاريخ البلاغ', default=fields.Datetime.now)
    customer_id = fields.Many2one('utility.customer', 'العميل')
    account_id = fields.Many2one('utility.customer', 'الحساب', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'العداد')
    tamper_type = fields.Selection([
        ('meter_bypass', 'تجاوز العداد'),
        ('meter_tamper', 'تلاعب بالعداد'),
        ('meter_reversal', 'عكس العداد'),
        ('unauthorized_connection', 'توصيل غير مصرّح'),
        ('meter_removal', 'إزالة العداد'),
        ('other', 'أخرى'),
    ], string='نوع التلاعب', required=True)
    description = fields.Text('الوصف', required=True)
    severity = fields.Selection([
        ('low', 'منخفضة'),
        ('medium', 'متوسطة'),
        ('high', 'عالية'),
        ('critical', 'حرجة'),
    ], string='الخطورة', default='medium')
    evidence_photos = fields.One2many('ir.attachment', 'res_id', string='صور الإثبات',
                                      domain=[('res_model', '=', 'utility.tamper.case')])
    evidence_notes = fields.Text('ملاحظات الإثبات')
    address = fields.Text('العنوان')
    reported_by = fields.Many2one('res.users', 'بلّغ بواسطة')
    assigned_to = fields.Many2one('res.users', 'مُعيّن لـ')
    estimated_loss = fields.Monetary('الخسارة التقديرية', currency_field='company_currency_id')
    penalty_amount = fields.Monetary('مبلغ الغرامة', currency_field='company_currency_id')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='العملة')
    inspector_id = fields.Many2one('res.users', 'المفتش المحقق')
    resolution_date = fields.Date('تاريخ القرار')
    resolution_notes = fields.Text('تفاصيل القرار')
    state = fields.Selection([
        ('reported', 'مُبلّغ'),
        ('investigating', 'قيد التحقيق'),
        ('proven', 'مُثبت'),
        ('dismissed', 'مرفوض'),
        ('settled', 'تمت التسوية'),
        ('legal', 'إجراء قانوني'),
    ], string='الحالة', default='reported')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('case_number', _('جديد')) == _('جديد'):
                vals['case_number'] = self.env['ir.sequence'].next_by_code('utility.tamper.case') or _('جديد')
        return super().create(vals_list)

    def write(self, vals):
        new_proven_cases = self.env['utility.tamper.case']
        if vals.get('state') == 'proven':
            new_proven_cases = self.filtered(lambda c: c.state != 'proven')

        res = super().write(vals)

        for case in new_proven_cases:
            if case.meter_id and 'utility.meter.log' in self.env:
                self.env['utility.meter.log'].with_context(allow_log_update=True)._create_log(
                    case.meter_id.id,
                    'tamper',
                    _('ثبوت تلاعب بالعداد بناءً على القضية %s') % case.case_number,
                    ref_record=case
                )
        return res
