from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class UtilityRouteAssignmentWizard(models.TransientModel):
    """
    Wizard ذكي لتعيين المشتركين للمسار بناءً على المحول.

    الخطوات:
      1. اختر المحول (أو محولات متعددة)
      2. يظهر تلقائياً مشتركو هذه المحولات
      3. حدد المشتركين المطلوبين
      4. حدد المستخدم المسؤول (كاشف/متحصل)
      5. احفظ → يُنشأ/يُحدَّث المسار تلقائياً
    """
    _name = 'utility.route.assignment.wizard'
    _description = 'معالج تعيين المشتركين بالمحول'

    # ── الخطوة 1: اختيار المحولات ────────────────────────────────────────────
    transformer_ids = fields.Many2many(
        'utility.transformer',
        'wizard_transformer_rel',
        'wizard_id', 'transformer_id',
        string='المحولات',
        required=True,
    )

    # ── الخطوة 2: المشتركون المتاحون (computed من المحولات) ──────────────────
    available_customer_ids = fields.Many2many(
        'utility.customer',
        'wizard_available_customer_rel',
        'wizard_id', 'customer_id',
        string='المشتركون المتاحون',
        compute='_compute_available_customers',
        store=True,
    )

    # ── الخطوة 3: المشتركون المحددون ─────────────────────────────────────────
    selected_customer_ids = fields.Many2many(
        'utility.customer',
        'wizard_selected_customer_rel',
        'wizard_id', 'customer_id',
        string='المشتركون المحددون',
    )

    customer_count = fields.Integer(
        'عدد المشتركين المتاحين',
        compute='_compute_available_customers',
        store=True,
    )

    selected_count = fields.Integer(
        'عدد المحددين',
        compute='_compute_selected_count',
    )

    # ── الخطوة 4: المستخدمون المسؤولون ──────────────────────────────────────
    user_ids = fields.Many2many(
        'res.users',
        'wizard_user_rel',
        'wizard_id', 'user_id',
        string='طاقم العمل (كاشف / متحصل)',
        domain="[('share', '=', False)]",
        required=True,
        help='المستخدمون المخصصون لهذا المسار — دورهم يُحدَّد من صلاحياتهم في Odoo',
    )

    supervisor_id = fields.Many2one(
        'res.users',
        string='المشرف',
        domain="[('share', '=', False)]",
    )

    # ── إعدادات المسار ───────────────────────────────────────────────────────
    route_id = fields.Many2one(
        'utility.route',
        string='المسار (موجود)',
        help='اختر مساراً موجوداً لتحديثه، أو اتركه فارغاً لإنشاء مسار جديد',
    )

    create_new_route = fields.Boolean(
        'إنشاء مسار جديد',
        compute='_compute_create_new_route',
    )

    new_route_name = fields.Char('اسم المسار الجديد')
    new_route_code = fields.Char('رمز المسار الجديد')

    assign_mode = fields.Selection([
        ('add', 'إضافة للمسار (مع الاحتفاظ بالحاليين)'),
        ('replace', 'استبدال (إزالة الحاليين وإضافة المحددين)'),
        ('move', 'نقل من مسارات أخرى'),
    ], string='طريقة التعيين', default='add', required=True)

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends('transformer_ids')
    def _compute_available_customers(self):
        for wizard in self:
            if not wizard.transformer_ids:
                wizard.available_customer_ids = False
                wizard.customer_count = 0
                continue

            # جلب المشتركين من خلال العدادات المرتبطة بالمحولات
            meters = self.env['utility.meter'].search([
                ('transformer_id', 'in', wizard.transformer_ids.ids),
                ('active', '=', True),
            ])
            customers = meters.mapped('customer_id').filtered(
                lambda c: c.active and c.id
            )
            wizard.available_customer_ids = customers
            wizard.customer_count = len(customers)

    @api.depends('selected_customer_ids')
    def _compute_selected_count(self):
        for wizard in self:
            wizard.selected_count = len(wizard.selected_customer_ids)

    @api.depends('route_id')
    def _compute_create_new_route(self):
        for wizard in self:
            wizard.create_new_route = not wizard.route_id

    # ── onchange ──────────────────────────────────────────────────────────────

    @api.onchange('transformer_ids')
    def _onchange_transformers(self):
        """عند تغيير المحولات، حدد جميع المشتركين تلقائياً"""
        self._compute_available_customers()
        # حدد الكل تلقائياً — يمكن للمستخدم إلغاء التحديد
        self.selected_customer_ids = self.available_customer_ids

    @api.onchange('route_id')
    def _onchange_route(self):
        """عند اختيار مسار موجود، جلب محوله وطاقم عمله"""
        if self.route_id:
            if self.route_id.transformer_id:
                self.transformer_ids = self.route_id.transformer_id
            self.user_ids = self.route_id.user_ids
            self.supervisor_id = self.route_id.supervisor_id

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_select_all(self):
        """تحديد جميع المشتركين المتاحين"""
        self.selected_customer_ids = self.available_customer_ids
        return {'type': 'ir.actions.act_window_close'} if False else self._reopen()

    def action_deselect_all(self):
        """إلغاء تحديد الكل"""
        self.selected_customer_ids = False
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm(self):
        """تطبيق التعيين"""
        self.ensure_one()

        if not self.selected_customer_ids:
            raise ValidationError('يجب تحديد مشترك واحد على الأقل.')

        if not self.user_ids:
            raise ValidationError('يجب تحديد مستخدم واحد على الأقل.')

        # إيجاد أو إنشاء المسار
        route = self._get_or_create_route()

        # تعيين طاقم العمل والمشرف
        route.user_ids = [(6, 0, self.user_ids.ids)]
        if self.supervisor_id:
            route.supervisor_id = self.supervisor_id

        # تعيين المشتركين
        if self.assign_mode == 'replace':
            # إزالة المشتركين القديمين وإضافة الجدد
            old_customers = route.customer_ids - self.selected_customer_ids
            old_customers.write({'route_id': False})
            self.selected_customer_ids.write({'route_id': route.id})

        elif self.assign_mode == 'add':
            # إضافة فقط
            self.selected_customer_ids.write({'route_id': route.id})

        elif self.assign_mode == 'move':
            # نقل من مسارات أخرى (يُزيل من المسارات القديمة)
            self.selected_customer_ids.write({'route_id': route.id})

        # رسالة في السجل
        route.message_post(
            body=_(
                'تم تعيين %(count)d مشترك بواسطة %(user)s '
                'من %(transformer_count)d محول. '
                'طاقم العمل: %(team)s'
            ) % {
                'count': len(self.selected_customer_ids),
                'user': self.env.user.name,
                'transformer_count': len(self.transformer_ids),
                'team': ', '.join(self.user_ids.mapped('name')),
            }
        )

        # فتح المسار بعد الحفظ
        return {
            'type': 'ir.actions.act_window',
            'name': 'المسار',
            'res_model': 'utility.route',
            'res_id': route.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_or_create_route(self):
        """إيجاد مسار موجود أو إنشاء جديد"""
        if self.route_id:
            return self.route_id

        # التحقق من البيانات المطلوبة للمسار الجديد
        if not self.new_route_name or not self.new_route_code:
            raise ValidationError(
                'يجب تحديد اسم ورمز للمسار الجديد، '
                'أو اختيار مسار موجود.'
            )

        # التحقق من عدم تكرار الرمز
        existing = self.env['utility.route'].search([
            ('code', '=', self.new_route_code),
        ], limit=1)
        if existing:
            raise ValidationError(
                f'رمز المسار "{self.new_route_code}" مستخدم بالفعل '
                f'في المسار: {existing.name}'
            )

        # إنشاء المسار
        transformer = self.transformer_ids[:1]
        return self.env['utility.route'].create({
            'name': self.new_route_name,
            'code': self.new_route_code,
            'transformer_id': transformer.id if transformer else False,
            'user_ids': [(6, 0, self.user_ids.ids)],
            'supervisor_id': self.supervisor_id.id if self.supervisor_id else False,
        })
