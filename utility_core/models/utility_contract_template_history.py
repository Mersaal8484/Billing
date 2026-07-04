from odoo import api, fields, models


class UtilityContractTemplateHistory(models.Model):
    _name = 'utility.contract.template.history'
    _description = 'سجل أسعار قالب العقد'
    _order = 'change_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='الوصف', compute='_compute_name', store=True)
    template_id = fields.Many2one(
        'utility.contract.template', 'قالب العقد',
        required=True, index=True, ondelete='cascade')

    change_date = fields.Datetime('تاريخ التغيير', default=fields.Datetime.now)
    old_price = fields.Float('السعر القديم (لكل kWh)')
    new_price = fields.Float('السعر الجديد (لكل kWh)')
    old_service_charge = fields.Float('رسم الخدمة الثابت القديم')
    new_service_charge = fields.Float('رسم الخدمة الثابت الجديد')
    reason = fields.Char('السبب')
    changed_by = fields.Many2one('res.users', 'بواسطة')

    @api.depends('template_id', 'change_date')
    def _compute_name(self):
        for rec in self:
            if rec.template_id and rec.change_date:
                rec.name = f"{rec.template_id.name} - {rec.change_date.date()}"
            else:
                rec.name = "تغيير تسعير"
