from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityFinancialSettlement(models.Model):
    _name = 'utility.financial.settlement'
    _description = 'Financial Settlement'
    _order = 'date desc'

    name = fields.Char('رقم التسوية المالية', default=lambda self: _('New'), readonly=True)
    account_id = fields.Many2one('utility.customer', 'حساب الكهرباء', required=True)
    customer_id = fields.Many2one('utility.customer', related='account_id', store=True)
    settlement_type = fields.Selection([
        ('credit', 'دائن (خصم للمشترك)'),
        ('debit', 'مدين (غرامة/إضافة على المشترك)'),
    ], string='نوع التسوية المالية', required=True)
    amount = fields.Float('مبلغ التسوية', required=True)
    reason = fields.Text('سبب التسوية المالية', required=True)
    date = fields.Date('تاريخ التسوية', default=fields.Date.today, readonly=True)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('applied', 'تم التطبيق'),
    ], string='الحالة', default='draft', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.financial.settlement') or _('New')
        return super().create(vals_list)

    def action_apply_settlement(self):
        self.ensure_one()
        if self.state == 'applied':
            raise ValidationError('تم تطبيق هذه التسوية بالفعل!')
            
        # تعديل رصيد حساب المشترك
        if self.settlement_type == 'credit':
            # دائن = خصم (يزيد الرصيد الدائن أو يقلل المديونية)
            self.account_id.balance += self.amount
        else:
            # مدين = إضافة مديونية (يقلل الرصيد أو يزيد الدين)
            self.account_id.balance -= self.amount
            
        self.state = 'applied'
        return True
