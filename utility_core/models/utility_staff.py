from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import re

PHONE_9_RE = re.compile(r'^\d{9}$')


class UtilityStaff(models.Model):
    _name = 'utility.staff'
    _description = 'موظف'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    active = fields.Boolean('نشط', default=True, tracking=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', 'المستخدم', tracking=True)
    employee_code = fields.Char('رمز الموظف', tracking=True)
    name = fields.Char('الاسم', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', 'الشريك المحاسبي للمحصل', check_company=True, tracking=True)
    team_id = fields.Many2one('utility.team', 'الفريق', tracking=True)
    user_role_id = fields.Many2one('utility.user.role', string='الدور', tracking=True)
    region_id = fields.Many2one(
        'utility.region', string='المنطقة',
        domain="[('type', '=', 'region')]", tracking=True)
    area_id = fields.Many2one(
        'utility.region', string='الفرع / المنطقة الفرعية',
        domain="[('type', '=', 'area')]", tracking=True)
    phone = fields.Char('الهاتف', tracking=True)
    mobile = fields.Char('الجوال', tracking=True)
    collection_journal_id = fields.Many2one(
        'account.journal', string='اليومية النقدية للتحصيل',
        domain="[('type', '=', 'cash')]",
        tracking=True,
        help='اليومية النقدية المخصصة لهذا المتحصل الميداني وتسجيل تحصيلاته')
    route_count = fields.Integer(string='عدد المسارات', compute='_compute_route_count')

    @api.onchange('area_id')
    def _onchange_area_id_set_region(self):
        for rec in self:
            if rec.area_id and rec.area_id.parent_id:
                rec.region_id = rec.area_id.parent_id

    @api.onchange('region_id')
    def _onchange_region_id_clear_area(self):
        for rec in self:
            if rec.area_id and rec.region_id and rec.area_id.parent_id != rec.region_id:
                rec.area_id = False

    def _compute_route_count(self):
        for record in self:
            routes = self.env['utility.route'].search([
                '|', ('inspector_ids', 'in', record.id),
                '|', ('cashier_ids', 'in', record.id),
                ('supervisor_id', '=', record.id)
            ])
            record.route_count = len(routes)

    def action_view_collection_journal(self):
        self.ensure_one()
        self._auto_create_collector_journal()
        if not self.collection_journal_id:
            return False
        return {
            'name': _('اليومية النقدية للمتحصل'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.journal',
            'res_id': self.collection_journal_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_assigned_routes(self):
        self.ensure_one()
        routes = self.env['utility.route'].search([
            '|', ('inspector_ids', 'in', self.id),
            '|', ('cashier_ids', 'in', self.id),
            ('supervisor_id', '=', self.id)
        ])
        return {
            'name': _('المسارات الميدانية للموظف'),
            'type': 'ir.actions.act_window',
            'res_model': 'utility.route',
            'domain': [('id', 'in', routes.ids)],
            'view_mode': 'tree,form',
            'target': 'current',
        }

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

    def _auto_create_collector_journal(self):
        """Auto-create a dedicated Cash Journal for field collectors and cashiers."""
        for record in self:
            is_collector = False
            if record.user_role_id:
                code = (record.user_role_id.code or '').lower()
                name = record.user_role_id.name or ''
                if code in ('collector', 'cashier') or any(kw in name for kw in ('متحصل', 'صندوق', 'محصل')):
                    is_collector = True
            else:
                # إذا لم يُحدد دور محدد، نعتبر كل موظف في جدول الموظفين الميدانيين مؤهلاً
                is_collector = True

            if is_collector and not record.collection_journal_id:
                code_suffix = str(record.id or record.employee_code or '001')[-4:]
                code = ('C%s' % code_suffix).upper()[:5]
                journal_name = 'يومية تحصيل - %s' % record.name
                existing = self.env['account.journal'].search([
                    ('company_id', '=', record.company_id.id),
                    ('type', '=', 'cash'),
                    '|', ('code', '=', code), ('name', '=', journal_name)
                ], limit=1)
                if not existing:
                    acc_name = 'حساب صندوق - %s' % record.name
                    cash_acc = self.env['account.account'].search([
                        ('name', '=', acc_name),
                        ('company_id', '=', record.company_id.id)
                    ], limit=1)
                    if not cash_acc:
                        code_num = str(record.id or 1).zfill(3)
                        cash_acc = self.env['account.account'].create({
                            'name': acc_name,
                            'code': '101%s' % code_num[-3:],
                            'account_type': 'asset_cash',
                            'company_id': record.company_id.id,
                        })
                    
                    manual_inbound = self.env['account.payment.method'].search([
                        ('payment_type', '=', 'inbound'),
                        ('code', '=', 'manual')
                    ], limit=1)
                    manual_outbound = self.env['account.payment.method'].search([
                        ('payment_type', '=', 'outbound'),
                        ('code', '=', 'manual')
                    ], limit=1)

                    in_vals = {'name': 'يدوي', 'payment_method_id': manual_inbound.id} if manual_inbound else None
                    out_vals = {'name': 'يدوي', 'payment_method_id': manual_outbound.id} if manual_outbound else None

                    LineModel = self.env['account.payment.method.line']
                    acc_field = 'payment_account_id' if hasattr(LineModel, 'payment_account_id') else ('outstanding_account_id' if hasattr(LineModel, 'outstanding_account_id') else False)
                    if acc_field and cash_acc:
                        if in_vals: in_vals[acc_field] = cash_acc.id
                        if out_vals: out_vals[acc_field] = cash_acc.id

                    inbound_lines = [(0, 0, in_vals)] if in_vals else []
                    outbound_lines = [(0, 0, out_vals)] if out_vals else []

                    existing = self.env['account.journal'].create({
                        'name': journal_name,
                        'code': code,
                        'type': 'cash',
                        'company_id': record.company_id.id,
                        'default_account_id': cash_acc.id if cash_acc else False,
                        'inbound_payment_method_line_ids': inbound_lines,
                        'outbound_payment_method_line_ids': outbound_lines,
                    })
                record.collection_journal_id = existing.id

            if record.collection_journal_id:
                journal = record.collection_journal_id
                company = journal.company_id
                # 1. ضمان وجود حسابات الدفعات والإيصالات المستحقة على الشركة
                if not company.account_journal_payment_debit_account_id or not company.account_journal_payment_credit_account_id:
                    outstanding_acc = self.env['account.account'].search([
                        ('name', 'ilike', 'مستحق'),
                        ('company_id', 'in', (company.id, False))
                    ], limit=1) or self.env['account.account'].search([
                        ('account_type', 'in', ('asset_current', 'asset_cash')),
                        ('company_id', 'in', (company.id, False))
                    ], limit=1)
                    if not outstanding_acc:
                        outstanding_acc = self.env['account.account'].create({
                            'name': 'حساب الإيصالات والدفعات المستحقة',
                            'code': '101200',
                            'account_type': 'asset_current',
                            'company_id': company.id,
                        })
                    c_vals = {}
                    if not company.account_journal_payment_debit_account_id:
                        c_vals['account_journal_payment_debit_account_id'] = outstanding_acc.id
                    if not company.account_journal_payment_credit_account_id:
                        c_vals['account_journal_payment_credit_account_id'] = outstanding_acc.id
                    if c_vals:
                        company.sudo().write(c_vals)

                # 2. ضمان أن الحساب النقدي لليومية مخصص باسم هذا الموظف وليس حساسية لموظف آخر
                j_vals = {}
                acc_name = 'حساب صندوق - %s' % record.name
                cash_acc = journal.default_account_id
                if not cash_acc or (record.name and record.name not in cash_acc.name):
                    cash_acc = self.env['account.account'].search([
                        ('name', '=', acc_name),
                        ('company_id', '=', company.id)
                    ], limit=1)
                    if not cash_acc:
                        code_num = str(record.id or 1).zfill(3)
                        cash_acc = self.env['account.account'].create({
                            'name': acc_name,
                            'code': '101%s' % code_num[-3:],
                            'account_type': 'asset_cash',
                            'company_id': company.id,
                        })
                    j_vals['default_account_id'] = cash_acc.id

                LineModel = self.env['account.payment.method.line']
                acc_field = 'payment_account_id' if hasattr(LineModel, 'payment_account_id') else ('outstanding_account_id' if hasattr(LineModel, 'outstanding_account_id') else False)
                target_out_acc = company.account_journal_payment_debit_account_id.id if company.account_journal_payment_debit_account_id else (cash_acc.id if cash_acc else False)

                if not journal.inbound_payment_method_line_ids:
                    manual_inbound = self.env['account.payment.method'].search([
                        ('payment_type', '=', 'inbound'),
                        ('code', '=', 'manual')
                    ], limit=1)
                    if manual_inbound:
                        m_line = {'name': 'يدوي', 'payment_method_id': manual_inbound.id}
                        if acc_field and target_out_acc: m_line[acc_field] = target_out_acc
                        j_vals['inbound_payment_method_line_ids'] = [(0, 0, m_line)]
                elif acc_field and target_out_acc:
                    for line in journal.inbound_payment_method_line_ids:
                        if not getattr(line, acc_field, False):
                            line.sudo().write({acc_field: target_out_acc})

                if not journal.outbound_payment_method_line_ids:
                    manual_outbound = self.env['account.payment.method'].search([
                        ('payment_type', '=', 'outbound'),
                        ('code', '=', 'manual')
                    ], limit=1)
                    if manual_outbound:
                        m_line = {'name': 'يدوي', 'payment_method_id': manual_outbound.id}
                        if acc_field and target_out_acc: m_line[acc_field] = target_out_acc
                        j_vals['outbound_payment_method_line_ids'] = [(0, 0, m_line)]
                elif acc_field and target_out_acc:
                    for line in journal.outbound_payment_method_line_ids:
                        if not getattr(line, acc_field, False):
                            line.sudo().write({acc_field: target_out_acc})

                if j_vals:
                    journal.sudo().write(j_vals)

                if record.user_id and record.user_id.collection_journal_id != journal:
                    record.user_id.sudo().write({'collection_journal_id': journal.id})

    def action_create_cash_journal(self):
        """Manual action to generate or re-assign a dedicated Cash Journal."""
        self.ensure_one()
        self._auto_create_collector_journal()
        if self.collection_journal_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('نجاح'),
                    'message': _('تم إنشاء وتخصيص اليومية النقدية (%s) للمتحصل بنجاح.') % self.collection_journal_id.name,
                    'sticky': False,
                }
            }

    def write(self, vals):
        res = super(UtilityStaff, self).write(vals)
        if 'user_role_id' in vals or 'user_id' in vals or 'name' in vals or 'collection_journal_id' in vals:
            for record in self:
                record._auto_create_collector_journal()
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
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super(UtilityStaff, self).create(vals_list)
        for record in records:
            record._auto_create_collector_journal()
            if record.user_id and record.user_role_id and record.user_role_id.group_ids:
                record.user_id.write({'groups_id': [(4, group.id) for group in record.user_role_id.group_ids]})
        return records
