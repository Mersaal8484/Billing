from odoo import api, fields, models

class UtilityMigrationMapping(models.Model):
    _name = 'utility.migration.mapping'
    _description = 'جدول ترميز البيانات'
    _rec_name = 'legacy_code'

    mapping_type = fields.Selection([
        ('region', 'المنطقة'),
        ('area', 'الفرع'),
        ('category', 'الفئة'),
        ('subscriber', 'نوع المشترك'),
        ('contract', 'قالب العقد'),
    ], string='نوع الترميز', required=True)
    
    legacy_code = fields.Char('الرمز القديم', required=True)
    
    # Odoo References
    region_id = fields.Many2one('utility.region', string='المنطقة (Odoo)')
    area_id = fields.Many2one('utility.region', string='الفرع (Odoo)')
    category_id = fields.Many2one('utility.subscriber.category', string='الفئة (Odoo)')
    subscriber_type_id = fields.Many2one('utility.subscriber', string='نوع المشترك (Odoo)')
    contract_template_id = fields.Many2one('utility.contract.template', string='قالب العقد (Odoo)')

    _sql_constraints = [
        ('unique_mapping', 'unique(mapping_type, legacy_code)', 'لا يمكن تكرار نفس الرمز القديم لنفس النوع!')
    ]

    @api.onchange('mapping_type')
    def _onchange_mapping_type(self):
        # Clear fields if type changes
        self.region_id = False
        self.area_id = False
        self.category_id = False
        self.subscriber_type_id = False
        self.contract_template_id = False
