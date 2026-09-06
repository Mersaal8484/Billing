from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class UtilityRoute(models.Model):
    _name = 'utility.route'
    _description = 'مسار / خط'
    _order = 'name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم المسار', required=True)
    code = fields.Char('رمز المسار', required=True)

    # ===== التسلسل التجاري: region → area → zone → route =====
    area_id = fields.Many2one('utility.region', 'المنطقة الفرعية', domain="[('type', '=', 'area')]")
    zone_id = fields.Many2one('utility.region', 'المنطقة التفصيلية', domain="[('type', '=', 'zone')]")
    region_id = fields.Many2one('utility.region', 'المنطقة', related='area_id.parent_id', store=True)

    # ===== تسلسل التوزيع: substation → feeder → transformer → route =====
    transformer_id = fields.Many2one('utility.transformer', 'المحول', index=True)
    feeder_id = fields.Many2one('utility.feeder', 'الفيدر / الخلية', related='transformer_id.feeder_id', store=True)
    substation_id = fields.Many2one('utility.substation', 'المحطة الفرعية', related='transformer_id.substation_id', store=True)

    customer_ids = fields.One2many('utility.customer', 'route_id', string='عقود المشتركين')
    customer_count = fields.Integer('عدد المشتركين', compute='_compute_customer_count', store=True)
    user_ids = fields.Many2many(
        'res.users', 'res_users_route_rel',
        'route_id', 'user_id',
        string='طاقم العمل (كاشف / محصل / مشرف)',
        help='جميع المستخدمين المعيّنين لهذا المسار — دور كل مستخدم '
             '(كاشف / محصل / مشرف) يُحدَّد تلقائياً من صلاحياته في النظام'
    )
    # Deprecated: حقل المشرف القديم — مُبقى في قاعدة البيانات للتوافق العكسي
    # لا تستخدمه في منطق جديد؛ أضف المشرف عبر user_ids بدلاً من ذلك.
    supervisor_id = fields.Many2one(
        'res.users',
        string='المشرف (حقل قديم - للتوافق)',
        help='حقل قديم — أضف المشرف عبر حقل طاقم العمل (user_ids).'
    )

    _sql_constraints = [
        ('unique_route_code_area', 'unique(code, area_id)', 'رمز المسار يجب أن يكون فريداً لكل منطقة!'),
    ]

    @api.onchange('transformer_id')
    def _onchange_transformer_set_distribution(self):
        for rec in self:
            if rec.transformer_id:
                rec.zone_id = rec.transformer_id.zone_region_id.id
                if rec.transformer_id.zone_region_id:
                    rec.area_id = rec.transformer_id.zone_region_id.parent_id.id
                    if rec.transformer_id.zone_region_id.parent_id:
                        rec.region_id = rec.transformer_id.zone_region_id.parent_id.parent_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            transformer_id = vals.get('transformer_id')
            if transformer_id:
                transformer = self.env['utility.transformer'].browse(transformer_id)
                vals.setdefault('zone_id', transformer.zone_region_id.id)
                vals.setdefault('area_id', transformer.area_id.id)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get('transformer_id') and 'zone_id' not in vals and 'area_id' not in vals:
            transformer = self.env['utility.transformer'].browse(vals['transformer_id'])
            vals['zone_id'] = transformer.zone_region_id.id
            vals['area_id'] = transformer.area_id.id
        return super().write(vals)

    @api.constrains('area_id', 'zone_id', 'transformer_id')
    def _check_route_hierarchy(self):
        for route in self:
            if route.zone_id and route.area_id and route.zone_id.parent_id != route.area_id:
                raise ValidationError(_('المنطقة التفصيلية للمسار يجب أن تتبع الفرع المحدد.'))
            transformer = route.transformer_id
            if transformer:
                if route.zone_id and transformer.zone_region_id != route.zone_id:
                    raise ValidationError(_('محول المسار يجب أن يطابق المنطقة التفصيلية للمسار.'))
                if route.area_id and transformer.area_id != route.area_id:
                    raise ValidationError(_('محول المسار يجب أن يطابق فرع المسار.'))

    @api.depends('customer_ids')
    def _compute_customer_count(self):
        for rec in self:
            rec.customer_count = len(rec.customer_ids)

    def action_add_customers_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'إضافة مشتركين',
            'res_model': 'utility.route.add.customer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_route_id': self.id},
        }

    def action_remove_customers_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'حذف مشتركين',
            'res_model': 'utility.route.remove.customer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_route_id': self.id},
        }


class UtilityRouteAddCustomerWizard(models.TransientModel):
    _name = 'utility.route.add.customer.wizard'
    _inherit = ['utility.dropdown.mixin']
    _description = 'إضافة مشتركين إلى مسار'

    route_id = fields.Many2one('utility.route', 'المسار', required=True, readonly=True)
    filter_same_area = fields.Boolean('تصفية حسب نطاق المسار فقط', default=True, help='عرض المشتركين التابعين لنفس الفرع/المنطقة للمسار فقط')
    customer_ids = fields.Many2many(
        'utility.customer', 'wizard_add_customer_rel', 'wizard_id', 'customer_id',
        string='المشتركين',
    )
    selected_count = fields.Integer('عدد المشتركين المحددين للإضافة', compute='_compute_counts')

    @api.onchange('route_id', 'filter_same_area')
    def _onchange_filter_same_area(self):
        domain = [('route_id', '=', False)]
        if self.filter_same_area and self.route_id:
            domain.extend(self._get_route_domain(
                region_id=self.route_id.region_id.id if self.route_id.region_id else False,
                area_id=self.route_id.area_id.id if self.route_id.area_id else False,
                zone_id=self.route_id.zone_id.id if self.route_id.zone_id else False,
            ))
        return {'domain': {'customer_ids': domain}}

    @api.depends('customer_ids')
    def _compute_counts(self):
        for wizard in self:
            wizard.selected_count = len(wizard.customer_ids)

    def action_add(self):
        self.ensure_one()
        if not (
            self.env.user.has_group('utility_core.group_utility_supervisor')
            or self.env.user.has_group('utility_core.group_utility_admin')
        ):
            raise AccessError(_('ليس لديك صلاحية إسناد المشتركين إلى المسارات.'))
        if self.customer_ids and self.route_id:
            self.customer_ids.write({'route_id': self.route_id.id})
        return {'type': 'ir.actions.act_window_close'}


class UtilityRouteRemoveCustomerWizard(models.TransientModel):
    _name = 'utility.route.remove.customer.wizard'
    _inherit = ['utility.dropdown.mixin']
    _description = 'حذف مشتركين من مسار'

    route_id = fields.Many2one('utility.route', 'المسار', required=True, readonly=True)
    customer_ids = fields.Many2many(
        'utility.customer', 'wizard_remove_customer_rel', 'wizard_id', 'customer_id',
        string='المشتركين',
    )
    selected_count = fields.Integer('عدد المشتركين المحددين للاستبعاد', compute='_compute_counts')

    @api.onchange('route_id')
    def _onchange_route_id(self):
        if self.route_id:
            return {'domain': {'customer_ids': [('route_id', '=', self.route_id.id)]}}
        return {'domain': {'customer_ids': [('id', '=', False)]}}

    @api.depends('customer_ids')
    def _compute_counts(self):
        for wizard in self:
            wizard.selected_count = len(wizard.customer_ids)

    def action_remove(self):
        self.ensure_one()
        if not (
            self.env.user.has_group('utility_core.group_utility_supervisor')
            or self.env.user.has_group('utility_core.group_utility_admin')
        ):
            raise AccessError(_('ليس لديك صلاحية إزالة المشتركين من المسارات.'))
        if self.customer_ids:
            self.customer_ids.write({'route_id': False})
        return {'type': 'ir.actions.act_window_close'}
