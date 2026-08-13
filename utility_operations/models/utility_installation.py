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
    meter_serial_snapshot = fields.Char(
        'الرقم التسلسلي للعداد (لقطة تاريخية)', readonly=True,
        help='الرقم التسلسلي المادي للعداد وقت التركيب (لقطة غير قابلة للتغيير).'
    )
    meter_serial = fields.Char(
        'الرقم التسلسلي للعداد', related='meter_serial_snapshot', readonly=True
    )
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

    @api.onchange('meter_id')
    def _onchange_meter_id_snapshot(self):
        if self.meter_id:
            self.meter_serial_snapshot = getattr(self.meter_id, 'serial_number', False) or self.meter_id._get_physical_serial()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('جديد')) == _('جديد'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.installation') or _('جديد')
            if 'meter_id' in vals and not vals.get('meter_serial_snapshot'):
                meter = self.env['utility.meter'].browse(vals['meter_id'])
                if meter:
                    vals['meter_serial_snapshot'] = getattr(meter, 'serial_number', False) or meter._get_physical_serial()
        return super().create(vals_list)
