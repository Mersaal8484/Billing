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
    role_ids = fields.Many2many(
        'utility.user.role',
        'utility_staff_role_rel',
        'staff_id',
        'role_id',
        string='الأدوار التشغيلية',
        tracking=True,
        help='الأدوار التشغيلية المعتمدة للموظف (مثل محصل، قارئ عدادات، فني).'
    )
    user_role_id = fields.Many2one(
        'utility.user.role',
        string='الدور (حقل قديم - للتوافق)',
        tracking=True,
        help='حقل قديم للتوافق - المصدر الحقيقي لصلاحيات وأدوار الموظف هو role_ids'
    )
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
    cash_account_id = fields.Many2one(
        'account.account', related='collection_journal_id.default_account_id',
        string='حساب صندوق المتحصل', store=True, readonly=True)
    route_count = fields.Integer(string='عدد المسارات', compute='_compute_route_count')

    def has_utility_role(self, code):
        self.ensure_one()
        return code in self.role_ids.mapped('code')

    def has_any_utility_role(self, *codes):
        self.ensure_one()
        assigned = set(self.role_ids.mapped('code'))
        return bool(assigned.intersection(codes))

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
            assigned_routes = record.user_id.assigned_route_ids if record.user_id else self.env['utility.route']
            legacy_routes = self.env['utility.route'].search([
                '|', ('inspector_ids', 'in', record.id),
                '|', ('cashier_ids', 'in', record.id),
                ('supervisor_id', '=', record.id)
            ])
            record.route_count = len(assigned_routes | legacy_routes)

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
        assigned_routes = self.user_id.assigned_route_ids if self.user_id else self.env['utility.route']
        legacy_routes = self.env['utility.route'].search([
            '|', ('inspector_ids', 'in', self.id),
            '|', ('cashier_ids', 'in', self.id),
            ('supervisor_id', '=', self.id)
        ])
        routes = assigned_routes | legacy_routes
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
        ('unique_collection_journal',
         'unique(collection_journal_id)',
         'لا يجوز مشاركة يومية التحصيل بين أكثر من متحصل.'),
    ]

    @api.constrains('collection_journal_id', 'company_id')
    def _check_collection_journal(self):
        for record in self.filtered('collection_journal_id'):
            journal = record.collection_journal_id
            if journal.type != 'cash':
                raise ValidationError(_('يومية المتحصل يجب أن تكون يومية نقدية.'))
            if journal.company_id != record.company_id:
                raise ValidationError(_('يومية المتحصل يجب أن تنتمي إلى نفس الشركة.'))
            if not journal.default_account_id:
                raise ValidationError(_('يومية المتحصل يجب أن تحتوي على حساب صندوق مستقل.'))
            duplicate = self.search([
                ('collection_journal_id', '=', journal.id),
                ('id', '!=', record.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'اليومية النقدية مستخدمة مسبقًا للمتحصل %s.'
                ) % duplicate.display_name)

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

    def _check_collector_role_removal(self, new_roles):
        """Ensure collector role cannot be removed if unresolved custody or collections exist."""
        for record in self:
            was_collector = record.has_utility_role('collector')
            will_be_collector = bool(new_roles and 'collector' in new_roles.mapped('code'))
            if was_collector and not will_be_collector:
                if 'utility.collection' in self.env:
                    open_collections = self.env['utility.collection'].search([
                        ('collector_id', '=', record.id),
                        ('state', 'not in', ('settled', 'cancelled')),
                    ], limit=1)
                    if open_collections:
                        raise ValidationError(_(
                            'لا يمكن إزالة دور المحصل لوجود تحصيلات أو عهد نقدية غير مسددة للموظف %s.'
                        ) % record.display_name)
                if 'utility.collection.settlement' in self.env:
                    open_settlements = self.env['utility.collection.settlement'].search([
                        ('collector_id', '=', record.id),
                        ('state', 'not in', ('deposited', 'reconciled', 'cancelled')),
                    ], limit=1)
                    if open_settlements:
                        raise ValidationError(_(
                            'لا يمكن إزالة دور المحصل لوجود تسويات عهدة نقدية مفتوحة للموظف %s.'
                        ) % record.display_name)

    def _auto_create_collector_journal(self):
        """Create a collection journal only for postpaid field collectors."""
        for record in self:
            is_collector = record.has_utility_role('collector')

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

            if is_collector and record.collection_journal_id:
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
                target_out_acc = cash_acc.id if cash_acc else False

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

    def _sync_user_groups(self, old_users=None):
        """Synchronize Utility role root groups to linked users cleanly respecting implied_ids."""
        Role = self.env['utility.user.role']
        all_role_groups = Role.search([]).mapped('group_ids')
        if not all_role_groups:
            return

        affected_users = self.mapped('user_id')
        if old_users:
            affected_users |= old_users

        for user in affected_users.filtered(lambda u: u.exists()):
            staff_records = self.search([('user_id', '=', user.id), ('active', '=', True)])
            target_groups = staff_records.mapped('role_ids.group_ids')
            groups_to_revoke = all_role_groups - target_groups

            vals = []
            for g in groups_to_revoke:
                if g in user.groups_id:
                    vals.append((3, g.id))
            for g in target_groups:
                if g not in user.groups_id:
                    vals.append((4, g.id))
            if vals:
                user.sudo().write({'groups_id': vals})

    def write(self, vals):
        if vals.get('collection_journal_id'):
            journal = self.env['account.journal'].browse(
                vals['collection_journal_id']).exists()
            duplicate = self.search([
                ('collection_journal_id', '=', journal.id),
                ('id', 'not in', self.ids),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'اليومية النقدية مستخدمة مسبقًا للمتحصل %s.'
                ) % duplicate.display_name)

        if 'role_ids' in vals:
            role_cmd = vals['role_ids']
            if role_cmd and isinstance(role_cmd, list):
                new_role_ids = []
                for cmd in role_cmd:
                    if cmd[0] in (4,):
                        new_role_ids.append(cmd[1])
                    elif cmd[0] in (6,):
                        new_role_ids = list(cmd[2])
                new_roles = self.env['utility.user.role'].browse(new_role_ids) if new_role_ids else self.env['utility.user.role']
                self._check_collector_role_removal(new_roles)

        old_users = self.mapped('user_id') if 'user_id' in vals else self.env['res.users']
        res = super(UtilityStaff, self).write(vals)

        if any(f in vals for f in ('role_ids', 'user_role_id', 'user_id', 'name', 'collection_journal_id', 'active')):
            for record in self:
                record._auto_create_collector_journal()
            self._sync_user_groups(old_users=old_users)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('user_role_id') and not vals.get('role_ids'):
                vals['role_ids'] = [(4, vals['user_role_id'])]
        records = super(UtilityStaff, self).create(vals_list)
        for record in records:
            record._auto_create_collector_journal()
        records._sync_user_groups()
        return records

    def init(self):
        super().init()
        # Safe, idempotent migration: populate role_ids from legacy user_role_id if present
        self.env.cr.execute("""
            CREATE TABLE IF NOT EXISTS utility_staff_role_rel (
                staff_id INTEGER NOT NULL REFERENCES utility_staff(id) ON DELETE CASCADE,
                role_id INTEGER NOT NULL REFERENCES utility_user_role(id) ON DELETE CASCADE,
                PRIMARY KEY (staff_id, role_id)
            );
            CREATE INDEX IF NOT EXISTS utility_staff_role_rel_staff_idx ON utility_staff_role_rel(staff_id);
            CREATE INDEX IF NOT EXISTS utility_staff_role_rel_role_idx ON utility_staff_role_rel(role_id);

            INSERT INTO utility_staff_role_rel (staff_id, role_id)
            SELECT id, user_role_id
            FROM utility_staff
            WHERE user_role_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM utility_staff_role_rel
                  WHERE staff_id = utility_staff.id AND role_id = utility_staff.user_role_id
              );
        """)
