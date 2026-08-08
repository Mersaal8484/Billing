from odoo import api, fields, models, _


class UtilityInstallation(models.Model):
    _name = 'utility.installation'
    _description = 'تركيبة'
    _rec_name = 'name'
    _order = 'installation_date desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('رقم التركيبة', required=True, index=True, default=lambda self: _('جديد'))
    service_order_id = fields.Many2one('utility.service.order', 'أمر الخدمة')
    customer_id = fields.Many2one('utility.customer', 'العميل', required=True)
    account_id = fields.Many2one('utility.customer', 'الحساب', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'العداد', required=True)
    meter_serial = fields.Char('الرقم التسلسلي للعداد')
    meter_type_id = fields.Many2one('utility.meter.type', 'نوع العداد')
    installation_date = fields.Datetime('تاريخ التركيب', default=fields.Datetime.now)
    installer_id = fields.Many2one('res.users', 'التركيب بواسطة')
    address = fields.Text('العنوان')
    seal_number = fields.Char('رقم الختم')
    notes = fields.Text('ملاحظات')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('installed', 'مُرَكّب'),
        ('verified', 'مُتحقّق'),
        ('failed', 'فشل'),
    ], string='الحالة', default='draft')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('جديد')) == _('جديد'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.installation') or _('جديد')
        return super().create(vals_list)
