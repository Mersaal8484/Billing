from odoo import api, fields, models, _


class UtilityRoute(models.Model):
    _name = 'utility.route'
    _description = 'مسار / خط'
    _order = 'name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم المسار', required=True)
    code = fields.Char('رمز المسار', required=True)
    area_id = fields.Many2one('utility.region', 'المنطقة الفرعية', domain="[('type', '=', 'area')]")
    zone_id = fields.Many2one('utility.region', 'المنطقة التفصيلية', domain="[('type', '=', 'zone')]")
    region_id = fields.Many2one('utility.region', 'المنطقة', related='area_id.parent_id', store=True)
    customer_ids = fields.One2many('utility.customer', 'route_id', string='عقود المشتركين')
    customer_count = fields.Integer('عدد المشتركين', compute='_compute_customer_count', store=True)
    inspector_ids = fields.Many2many(
        'utility.staff', 'route_inspector_rel', 'route_id', 'staff_id',
        string='الكشافون',
        domain="[('user_role_id.code', '=', 'inspector')]",
    )
    cashier_ids = fields.Many2many(
        'utility.staff', 'route_cashier_rel', 'route_id', 'staff_id',
        string='المحصلون',
        domain="[('user_role_id.code', '=', 'cashier')]",
    )
    supervisor_id = fields.Many2one('utility.staff', string='المشرف', domain="[('user_role_id.code', '=', 'supervisor')]")

    _sql_constraints = [
        ('unique_route_code_area', 'unique(code, area_id)', 'رمز المسار يجب أن يكون فريداً لكل منطقة!'),
    ]

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
    _description = 'إضافة مشتركين إلى مسار'

    route_id = fields.Many2one('utility.route', 'المسار', required=True, readonly=True)
    customer_ids = fields.Many2many(
        'utility.customer', 'wizard_add_customer_rel', 'wizard_id', 'customer_id',
        string='المشتركين',
        domain="[('route_id', '=', False)]",
    )

    def action_add(self):
        self.ensure_one()
        if self.customer_ids:
            self.route_id.write({
                'customer_ids': [(4, c.id) for c in self.customer_ids]
            })
        return {'type': 'ir.actions.act_window_close'}


class UtilityRouteRemoveCustomerWizard(models.TransientModel):
    _name = 'utility.route.remove.customer.wizard'
    _description = 'حذف مشتركين من مسار'

    route_id = fields.Many2one('utility.route', 'المسار', required=True, readonly=True)
    customer_ids = fields.Many2many(
        'utility.customer', 'wizard_remove_customer_rel', 'wizard_id', 'customer_id',
        string='المشتركين',
        domain="[('route_id', '=', route_id)]",
    )

    def action_remove(self):
        self.ensure_one()
        if self.customer_ids:
            self.route_id.write({
                'customer_ids': [(3, c.id) for c in self.customer_ids]
            })
        return {'type': 'ir.actions.act_window_close'}
