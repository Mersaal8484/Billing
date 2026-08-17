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

    @staticmethod
    def _simulate_m2m_ids(current_ids, commands):
        """Accurately compute resulting IDs from any Odoo Many2many command list."""
        if not commands:
            return set(current_ids)
        res = set(current_ids)
        for cmd in commands:
            if not isinstance(cmd, (list, tuple)) or not cmd:
                continue
            c_type = cmd[0]
            if c_type == 0:  # (0, 0, vals)
                pass
            elif c_type == 1:  # (1, id, vals)
                res.add(cmd[1])
            elif c_type in (2, 3):  # (2, id) delete, (3, id) unlink
                res.discard(cmd[1])
            elif c_type == 4:  # (4, id) link
                res.add(cmd[1])
            elif c_type == 5:  # (5,) unlink all
                res.clear()
            elif c_type == 6:  # (6, 0, ids) replace
                res = set(cmd[2])
        return res

    def _check_collector_role_removal(self, new_role_ids):
        """Ensure collector role cannot be removed if unresolved custody or collections exist."""
        Role = self.env['utility.user.role']
        for record in self:
            was_collector = record.has_utility_role('collector')
            new_roles = Role.browse(list(new_role_ids)) if new_role_ids else Role
            will_be_collector = bool(new_roles and 'collector' in new_roles.mapped('code'))
            if was_collector and not will_be_collector:
                if 'utility.collection' in self.env:
                    open_collections = self.env['utility.collection'].search([
                        ('collector_id', '=', record.id),
                        ('state', 'not in', ('settled', 'deposited', 'reconciled', 'cancelled')),
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
        """No-op: automatic collector journal provisioning has been removed.

        Rationale (Phase 5, P0): creating account.account and account.journal
        records silently during staff.create() or staff.write() violates the
        production invariant that no Chart-of-Accounts mutation may occur at
        runtime without explicit administrator action.

        To provision a collector journal, use the explicit admin action:
            utility.staff form view → button 'إنشاء يومية التحصيل'
            (action_create_cash_journal) — protected by Admin/Accounting Manager.
        """
        pass

    def action_create_cash_journal(self):

        """Explicit admin action to provision a dedicated Cash Journal for this collector.

        Protected: requires Utility Admin or Accounting Manager group.
        Idempotent: if a journal already exists, opens it without creating another.
        """
        self.ensure_one()
        if not (self.env.user.has_group('utility_core.group_utility_admin')
                or self.env.user.has_group('base.group_account_manager')):
            raise AccessError(_(
                'إنشاء يومية التحصيل يستلزم صلاحية مدير النظام أو مدير المحاسبة.'
            ))
        # ── If journal already assigned, open it ──────────────────────────────
        if self.collection_journal_id:
            return {
                'name': _('اليومية النقدية للمتحصل'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.journal',
                'res_id': self.collection_journal_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        # ── Provision a new journal — explicit admin path only ────────────────
        if not self.has_utility_role('collector'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('تنبيه'),
                    'message': _('الموظف لا يملك دور المتحصل. لا يمكن إنشاء يومية تحصيل.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }
        company = self.company_id
        code_suffix = str(self.id or self.employee_code or '001')[-4:]
        code = ('C%s' % code_suffix).upper()[:5]
        journal_name = 'يومية تحصيل - %s' % self.name

        # Idempotency: search before creating
        existing_journal = self.env['account.journal'].search([
            ('company_id', '=', company.id),
            ('type', '=', 'cash'),
            '|', ('code', '=', code), ('name', '=', journal_name),
        ], limit=1)

        if not existing_journal:
            acc_name = 'حساب صندوق - %s' % self.name
            cash_acc = self.env['account.account'].search([
                ('name', '=', acc_name),
                ('company_id', '=', company.id),
            ], limit=1)
            if not cash_acc:
                code_num = str(self.id or 1).zfill(3)
                cash_acc = self.env['account.account'].create({
                    'name': acc_name,
                    'code': '101%s' % code_num[-3:],
                    'account_type': 'asset_cash',
                    'company_id': company.id,
                })
            existing_journal = self.env['account.journal'].create({
                'name': journal_name,
                'code': code,
                'type': 'cash',
                'company_id': company.id,
                'default_account_id': cash_acc.id,
            })

        self.collection_journal_id = existing_journal.id
        self.message_post(body=_(
            'تم إنشاء يومية التحصيل %s بواسطة %s.'
        ) % (existing_journal.name, self.env.user.name))
        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('نجاح'),
                    'message': _('تم إنشاء وتخصيص اليومية النقدية (%s) للمتحصل بنجاح.') % self.collection_journal_id.name,
                    'sticky': False,
                }
            }

    @api.model
    def _get_implied_group_closure(self, groups):
        """Recursively compute all implied groups down the hierarchy without relying on unstandardized fields."""
        if not groups:
            return self.env['res.groups']
        result = groups
        pending = groups
        while pending:
            implied = pending.mapped('implied_ids') - result
            if not implied:
                break
            result |= implied
            pending = implied
        return result

    def _sync_user_groups(self, old_users=None):
        """Synchronize Utility role root groups to linked users cleanly respecting recursive implied_ids."""
        Role = self.env['utility.user.role']
        all_role_groups = Role.search([]).mapped('group_ids')
        if not all_role_groups:
            return

        affected_users = self.mapped('user_id')
        if old_users:
            affected_users |= old_users

        for user in affected_users.filtered(lambda u: u.exists()):
            staff_records = self.search([('user_id', '=', user.id), ('active', '=', True)])
            target_root_groups = staff_records.mapped('role_ids.group_ids')

            # Calculate recursive closure of all groups implied by the target root groups
            implied_closure = self._get_implied_group_closure(target_root_groups)

            # Revoke role root groups only if not in target root groups AND not implied by any target role
            groups_to_revoke = (all_role_groups - target_root_groups) - implied_closure

            vals = []
            for g in groups_to_revoke:
                if g in user.groups_id:
                    vals.append((3, g.id))
            for g in target_root_groups:
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
                for record in self:
                    new_role_ids = self._simulate_m2m_ids(record.role_ids.ids, role_cmd)
                    record._check_collector_role_removal(new_role_ids)

        old_users = self.mapped('user_id') if 'user_id' in vals else self.env['res.users']
        res = super(UtilityStaff, self).write(vals)

        # Note: _auto_create_collector_journal() removed from write() path (Phase 5 P0).
        # Journal provisioning is now explicit-only via action_create_cash_journal().
        if any(f in vals for f in ('role_ids', 'user_role_id', 'user_id', 'active')):
            self._sync_user_groups(old_users=old_users)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('user_role_id') and not vals.get('role_ids'):
                vals['role_ids'] = [(4, vals['user_role_id'])]
        records = super(UtilityStaff, self).create(vals_list)
        # Note: _auto_create_collector_journal() removed from create() path (Phase 5 P0).
        # Journal provisioning is now explicit-only via action_create_cash_journal().
        records._sync_user_groups()
        return records
