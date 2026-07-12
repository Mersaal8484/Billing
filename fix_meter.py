import sys
path = r'c:\odoo\odoo\odoo\utility_erp\utility_core\models\utility_meter.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
lines = lines[:421]
new_code = '''    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('meter_number', _('جديد')) == _('جديد'):
                vals['meter_number'] = self.env['ir.sequence'].next_by_code('utility.meter') or _('جديد')
        return super().create(vals_list)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('meter_number', operator, name), ('serial_number', operator, name)]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)

    def name_get(self):
        result = []
        for meter in self:
            name = '[%s]' % meter.meter_number
            if hasattr(meter, 'connection_type'):
                ct = meter.connection_type
                if ct == 'subscriber' and meter.customer_id and meter.customer_id.partner_id:
                    name += ' - %s' % meter.customer_id.partner_id.name
                elif ct == 'private_transformer' and meter.linked_private_transformer_id:
                    name += ' - %s' % meter.linked_private_transformer_id.name
                elif ct == 'transformer' and meter.linked_transformer_id:
                    name += ' - %s' % meter.linked_transformer_id.name
                elif ct == 'feeder' and meter.linked_feeder_id:
                    name += ' - %s' % meter.linked_feeder_id.name
            result.append((meter.id, name))
        return result

    def write(self, vals):
        for meter in self:
            if 'status_id' in vals and vals.get('status_id') != meter.status_id.id:
                new_status = self.env['utility.meter.status'].browse(vals['status_id']) if vals.get('status_id') else None
                desc = f"تغيرت حالة العداد من {meter.status_id.name if meter.status_id else 'غير محدد'} إلى {new_status.name if new_status else 'غير محدد'}"
                if 'utility.meter.log' in self.env:
                    self.env['utility.meter.log'].with_context(allow_log_update=True)._create_log(
                        meter.id, 'status_change', desc, customer_id=meter.customer_id
                    )
            if 'customer_id' in vals and vals.get('customer_id') != meter.customer_id.id:
                old_cust = meter.customer_id.name if meter.customer_id else 'غير محدد'
                new_cust = self.env['utility.customer'].browse(vals['customer_id']).name if vals.get('customer_id') else 'غير محدد'
                desc = f"تم نقل العداد من العميل {old_cust} إلى العميل {new_cust}"
                if 'utility.meter.log' in self.env:
                    self.env['utility.meter.log'].with_context(allow_log_update=True)._create_log(
                        meter.id, 'transfer', desc, customer_id=vals.get('customer_id')
                    )
        return super().write(vals)


class UtilityMeterType(models.Model):
    _name = 'utility.meter.type'
    _description = 'نوع العداد'
    _order = 'name'

    name = fields.Char('الاسم', required=True)
    code = fields.Char('الرمز', required=True)
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور')
    description = fields.Text('الوصف')


class UtilityMeterModel(models.Model):
    _name = 'utility.meter.model'
    _description = 'موديل العداد'
    _order = 'name'

    name = fields.Char('الاسم', required=True)
    manufacturer = fields.Char('الشركة المصنّعة')
    meter_type_id = fields.Many2one('utility.meter.type', 'النوع')
    sts_supported = fields.Boolean('يدعم STS')
    communication_types = fields.Char('أنواع الاتصال')
    description = fields.Text('الوصف')
    product_id = fields.Many2one(
        'product.product', 'المنتج',
        help='المنتج الذي يمثل هذا الموديل في نظام المخزون والمحاسبة',
    )

    def action_open_product(self):
        self.ensure_one()
        if self.product_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'المنتج',
                'res_model': 'product.product',
                'res_id': self.product_id.id,
                'view_mode': 'form',
                'target': 'current',
            }


class UtilityMeterStatus(models.Model):
    _name = 'utility.meter.status'
    _description = 'حالة العداد'
    _order = 'sequence, name'

    name = fields.Char('الاسم', required=True)
    code = fields.Char('الرمز', required=True)
    sequence = fields.Integer('التسلسل')
    description = fields.Text('الوصف')
'''
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
    f.write(new_code)
