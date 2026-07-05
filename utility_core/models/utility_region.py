from odoo import api, fields, models
from .utility_date_range import BILLING_PERIOD_TYPES


class UtilityRegion(models.Model):
    _name = 'utility.region'
    _description = 'منطقة'
    _order = 'name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('الاسم', required=True, index=True)
    code = fields.Char('الرمز', required=True, index=True)
    
    type = fields.Selection([
        ('region', 'منطقة'),
        ('area', 'منطقة فرعية'),
        ('zone', 'منطقة تفصيلية'),
    ], string='النوع', default='region', required=True)
    
    parent_id = fields.Many2one('utility.region', string='العنصر الأب', index=True, ondelete='cascade')
    child_ids = fields.One2many('utility.region', 'parent_id', string='العناصر الفرعية')
    
    area_ids = fields.One2many('utility.region', 'parent_id', string='المناطق', domain=[('type', '=', 'area')])
    zone_ids = fields.One2many('utility.region', 'parent_id', string='النواحي', domain=[('type', '=', 'zone')])
    
    area_count = fields.Integer('عدد المناطق الفرعية', compute='_compute_area_count', store=True)
    zone_count = fields.Integer('عدد المناطق التفصيلية', compute='_compute_zone_count', store=True)
    recurring_rule_type = fields.Selection(
        BILLING_PERIOD_TYPES,
        string='نوع دورة الفوترة',
        default='monthly',
        required=True
    )
    
    cash_journal_id = fields.Many2one('account.journal', string='يومية الصندوق', domain=[('type', '=', 'cash')], help='يومية الصندوق الخاصة بهذه المنطقة')
    bank_journal_ids = fields.Many2many(
        'account.journal', 
        'utility_region_bank_journal_rel', 
        'region_id', 
        'journal_id', 
        string='الحسابات البنكية', 
        domain=[('type', '=', 'bank')],
        help='اليوميات البنكية التابعة لهذه المنطقة'
    )
    financial_manager_id = fields.Many2one('res.users', string='المدير المالي للمنطقة', help='المسؤول المالي عن هذه المنطقة')

    transformer_origin_id = fields.Many2one('utility.transformer', 'منشأ من محول',
        readonly=True, copy=False,
        help='إذا كان هذا الـ zone منشأً تلقائياً من محول، لا يمكن تعديله يدوياً')

    _sql_constraints = [
        ('unique_code_parent_company', 'unique(code, parent_id, company_id)', 'الرمز يجب أن يكون فريداً لكل عنصر أب/شركة!'),
    ]

    @api.depends('area_ids')
    def _compute_area_count(self):
        for r in self:
            r.area_count = len(r.area_ids)

    @api.depends('zone_ids')
    def _compute_zone_count(self):
        for r in self:
            r.zone_count = len(r.zone_ids)
