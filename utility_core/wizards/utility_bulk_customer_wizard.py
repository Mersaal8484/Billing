from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class UtilityBulkCustomerWizard(models.TransientModel):
    _name = 'utility.bulk.customer.wizard'
    _description = 'معالج الإنشاء المجمّع للحسابات والعدادات'

    partner_id = fields.Many2one('res.partner', string='المالك (العميل الأساسي)', required=True)
    
    category_id = fields.Many2one('utility.subscriber.category', string='فئة المشترك', required=True)
    subscriber_id = fields.Many2one('utility.subscriber', string='نوع المشترك', required=True, domain="[('category_id', '=', category_id)]")
    contract_template_id = fields.Many2one('utility.contract.template', string='قالب العقد', required=True)
    
    utility_region_id = fields.Many2one('utility.region', string="المنطقة التشغيلية", domain="[('type', '=', 'region')]")
    utility_area_id = fields.Many2one('utility.region', string="الفرع التشغيلي", domain="[('type', '=', 'area'), ('parent_id', '=', utility_region_id)]")
    transformer_zone_id = fields.Many2one('utility.region', string="نطاق المحول", domain="[('type', '=', 'zone'), ('parent_id', '=', utility_area_id)]")
    
    cell_id = fields.Many2one('utility.feeder', string='الخلية / الفيدر', domain="[('active', '=', True)]")
    transformer_id = fields.Many2one('utility.transformer', string='المحول', domain="[('active', '=', True)]")
    route_id = fields.Many2one('utility.route', string='خط السير')

    line_ids = fields.One2many('utility.bulk.customer.wizard.line', 'wizard_id', string='الحسابات')

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.utility_region_id = self.partner_id.region_id
            self.utility_area_id = self.partner_id.area_id
            self.transformer_zone_id = self.partner_id.zone_id

    def action_create_bulk_accounts(self):
        self.ensure_one()
        if not self.line_ids:
            raise ValidationError(_('يجب إدخال حساب واحد على الأقل في القائمة.'))
            
        Customer = self.env['utility.customer']
        Meter = self.env['utility.meter']
        
        created_customers = self.env['utility.customer']
        
        for idx, line in enumerate(self.line_ids, start=1):
            account_name = line.name or f"{self.partner_id.name} - حساب {idx}"
            
            # Create Customer
            customer_vals = {
                'partner_id': self.partner_id.id,
                'category_id': self.category_id.id,
                'subscriber_id': self.subscriber_id.id,
                'contract_template_id': self.contract_template_id.id,
                'cell_id': self.cell_id.id if self.cell_id else False,
                'transformer_id': self.transformer_id.id if self.transformer_id else False,
                'route_id': self.route_id.id if self.route_id else False,
                'state': 'active',
            }
            customer = Customer.create(customer_vals)
            
            # Update sequence/name if necessary
            customer.name = account_name
            created_customers += customer
            
            # Create Meter
            if line.meter_serial:
                meter_vals = {
                    'meter_number': line.meter_serial,
                    'product_id': line.meter_product_id.id if line.meter_product_id else False,
                    'meter_type_id': line.meter_type_id.id if line.meter_type_id else False,
                    'communication_type': line.communication_type,
                    'customer_id': customer.id,
                    'initial_reading': line.initial_reading,
                    'state': 'in_use',
                }
                meter = Meter.create(meter_vals)
                customer.meter_id = meter.id
                
        return {
            'name': _('الحسابات المنشأة'),
            'type': 'ir.actions.act_window',
            'res_model': 'utility.customer',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created_customers.ids)],
        }


class UtilityBulkCustomerWizardLine(models.TransientModel):
    _name = 'utility.bulk.customer.wizard.line'
    _description = 'أسطر الإدخال المجمّع للحسابات'

    wizard_id = fields.Many2one('utility.bulk.customer.wizard', required=True, ondelete='cascade')
    name = fields.Char(string='اسم الحساب المخصص (اختياري)')
    meter_serial = fields.Char(string='الرقم التسلسلي للعداد', required=True)
    meter_product_id = fields.Many2one('product.product', string='منتج العداد', domain="[('detailed_type', '=', 'product'), ('categ_id.name', 'ilike', 'عداد')]")
    meter_type_id = fields.Many2one('utility.meter.type', string='النوع (فاز)')
    communication_type = fields.Selection([
        ('rf', 'RF'),
        ('plc', 'PLC'),
        ('gprs', 'GPRS/3G/4G'),
        ('nb_iot', 'NB-IoT'),
        ('none', 'بدون اتصال (Manual)'),
    ], string='نوع الاتصال', default='rf')
    initial_reading = fields.Float(string='قراءة الافتتاح', default=0.0)
