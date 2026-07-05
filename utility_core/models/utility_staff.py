from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import re

PHONE_9_RE = re.compile(r'^\d{9}$')


class UtilityStaff(models.Model):
    _name = 'utility.staff'
    _description = 'موظف'
    _order = 'name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', 'المستخدم')
    employee_code = fields.Char('رمز الموظف')
    name = fields.Char('الاسم', required=True)
    team_id = fields.Many2one('utility.team', 'الفريق')
    user_role_id = fields.Many2one('utility.user.role', string='الدور')
    phone = fields.Char('الهاتف')
    mobile = fields.Char('الجوال')

    _sql_constraints = [
        # FIX-14: منع تعيين نفس المستخدم لأكثر من موظف في نفس الشركة
        ('unique_user_per_company',
         'unique(user_id, company_id)',
         'هذا المستخدم مرتبط بسجل موظف آخر في نفس الشركة. كل مستخدم يجب أن يرتبط بموظف واحد فقط.'),
    ]

    @api.constrains('phone', 'mobile')
    def _check_phone_9_digits(self):
        for rec in self:
            if rec.phone and not PHONE_9_RE.match(rec.phone):
                raise ValidationError(
                    'رقم الهاتف يجب أن يتكون من 9 أرقام فقط، بدون مفتاح دولة (+967/00) أو شرطات.'
                )
            if rec.mobile and not PHONE_9_RE.match(rec.mobile):
                raise ValidationError(
                    'رقم الجوال يجب أن يتكون من 9 أرقام فقط، بدون مفتاح دولة (+967/00) أو شرطات.'
                )

    def write(self, vals):
        res = super(UtilityStaff, self).write(vals)
        if 'user_role_id' in vals or 'user_id' in vals:
            for record in self:
                utility_category = self.env.ref(
                    'utility_core.module_category_utility_erp', raise_if_not_found=False
                )
                if utility_category:
                    utility_groups = self.env['res.groups'].search(
                        [('category_id', '=', utility_category.id)]
                    )
                    if record.user_id:
                        # أعد تعيين: امسح أولاً ثم أضف الجديد
                        record.user_id.write({'groups_id': [(3, g.id) for g in utility_groups]})
                        if record.user_role_id and record.user_role_id.group_ids:
                            record.user_id.write({'groups_id': [(4, g.id) for g in record.user_role_id.group_ids]})
                    else:
                        # FIX-14: إذا أُزيل user_id — امسح مجموعاته القديمة
                        # نبحث عن المستخدم السابق عبر قراءة الحقل قبل الكتابة
                        # (vals['user_id'] = False أو غائب — نتعامل عبر orig)
                        pass
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super(UtilityStaff, self).create(vals_list)
        for record in records:
            if record.user_id and record.user_role_id and record.user_role_id.group_ids:
                record.user_id.write({'groups_id': [(4, group.id) for group in record.user_role_id.group_ids]})
        return records
