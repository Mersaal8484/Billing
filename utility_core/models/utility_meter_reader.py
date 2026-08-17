from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMeterReader(models.Model):
    _name = 'utility.meter.reader'
    _description = 'كاشف قراءة العدادات'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    active = fields.Boolean('نشط', default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', 'الشركة',
        default=lambda self: self.env.company,
    )
    name = fields.Char('اسم الكاشف', required=True, tracking=True)
    code = fields.Char('رمز الكاشف', tracking=True)
    user_id = fields.Many2one(
        'res.users', 'حساب الدخول',
        required=True, tracking=True,
        help='حساب المستخدم الذي يستخدمه الكاشف لتسجيل الدخول في التطبيق',
    )
    mobile = fields.Char('رقم الجوال', tracking=True)
    staff_id = fields.Many2one(
        'utility.staff', 'سجل الموظف',
        tracking=True,
        help='ربط اختياري بسجل موظف موجود في النظام',
    )
    route_ids = fields.Many2many(
        'utility.route',
        'meter_reader_route_rel',
        'reader_id', 'route_id',
        string='المسارات المخصصة',
        tracking=True,
    )
    customer_count = fields.Integer(
        'عدد المشتركين',
        compute='_compute_customer_count',
        store=False,
    )

    _sql_constraints = [
        ('unique_user_id', 'unique(user_id)',
         'هذا المستخدم مرتبط بكاشف آخر. كل مستخدم يجب أن يرتبط بكاشف واحد فقط.'),
    ]

    @api.depends('route_ids')
    def _compute_customer_count(self):
        for reader in self:
            if reader.route_ids:
                reader.customer_count = self.env['utility.customer'].search_count([
                    ('route_id', 'in', reader.route_ids.ids),
                ])
            else:
                reader.customer_count = 0

    def _sync_user_routes(self):
        """تحديث assigned_route_ids في res.users ليطابق مسارات الكاشف."""
        for reader in self.filtered('user_id'):
            reader.user_id.sudo().write({
                'assigned_route_ids': [(6, 0, reader.route_ids.ids)],
            })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # تأكد من إضافة مجموعة قارئ العدادات للمستخدم
        meter_reader_group = self.env.ref(
            'utility_core.group_utility_meter_reader', raise_if_not_found=False)
        for reader in records:
            if reader.user_id and meter_reader_group:
                reader.user_id.sudo().write({
                    'groups_id': [(4, meter_reader_group.id)],
                })
        records._sync_user_routes()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'route_ids' in vals:
            self._sync_user_routes()
        if 'user_id' in vals:
            meter_reader_group = self.env.ref(
                'utility_core.group_utility_meter_reader', raise_if_not_found=False)
            for reader in self.filtered('user_id'):
                if meter_reader_group:
                    reader.user_id.sudo().write({
                        'groups_id': [(4, meter_reader_group.id)],
                    })
            self._sync_user_routes()
        return res

    def action_view_customers(self):
        self.ensure_one()
        return {
            'name': _('مشتركو الكاشف: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'utility.customer',
            'view_mode': 'tree,form',
            'domain': [('route_id', 'in', self.route_ids.ids)],
            'context': {'default_route_id': self.route_ids[:1].id if self.route_ids else False},
        }

    def action_view_routes(self):
        self.ensure_one()
        return {
            'name': _('مسارات الكاشف: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'utility.route',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.route_ids.ids)],
        }
