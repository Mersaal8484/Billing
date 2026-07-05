from odoo import api, fields, models, _


class UtilityConnection(models.Model):
    _name = 'utility.connection'
    _description = 'توصيلة كهرباء'
    _order = 'id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('رقم التوصيلة', default=lambda self: _('جديد'))
    customer_id = fields.Many2one('utility.customer', 'العميل', required=True)
    account_id = fields.Many2one('utility.customer', 'الحساب', related='customer_id', store=True)
    connection_type = fields.Many2one('utility.connection.type', 'نوع التوصيلة')
    meter_id = fields.Many2one('utility.meter', 'العداد')
    connection_date = fields.Date('تاريخ التوصيلة')
    status = fields.Selection([
        ('active', 'نشط'),
        ('disconnected', 'مفصول'),
        ('suspended', 'معلّق'),
    ], string='الحالة', default='active')
    address = fields.Text('العنوان')
    notes = fields.Text('ملاحظات')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('جديد')) == _('جديد'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.connection') or _('جديد')
        return super().create(vals_list)


class UtilityConnectionType(models.Model):
    _name = 'utility.connection.type'
    _description = 'نوع التوصيلة'
    _order = 'name'

    name = fields.Char('الاسم', required=True)
    code = fields.Char('الرمز', required=True)
    voltage_level = fields.Selection([
        ('lv', 'جهد منخفض'),
        ('mv', 'جهد متوسط'),
        ('hv', 'جهد عالي'),
    ], string='مستوى الجهد')
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور')
    description = fields.Text('الوصف')

