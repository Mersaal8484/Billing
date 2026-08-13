from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityServiceOrder(models.Model):
    _name = 'utility.service.order'
    _description = 'أمر خدمة'
    _rec_name = 'order_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_requested desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    order_number = fields.Char('رقم الأمر', required=True, index=True, default=lambda self: _('جديد'))
    date_requested = fields.Datetime('تاريخ الطلب', default=fields.Datetime.now)
    date_scheduled = fields.Datetime('التاريخ المجدول')
    date_completed = fields.Datetime('تاريخ الإكمال')
    service_type = fields.Selection([
        ('new_connection', 'توصيلة جديدة'),
        ('meter_replacement', 'استبدال عداد'),
        ('meter_removal', 'إزالة عداد'),
        ('meter_test', 'فحص عداد'),
        ('inspection', 'تفتيش'),
        ('disconnection', 'فصل'),
        ('reconnection', 'إعادة توصيل'),
        ('tamper_investigation', 'تحقيق تلاعب'),
        ('site_survey', 'مسح موقع'),
        ('maintenance', 'صيانة'),
        ('other', 'أخرى'),
    ], string='نوع الخدمة', required=True)
    priority = fields.Selection([
        ('low', 'منخفضة'),
        ('normal', 'عادية'),
        ('high', 'عالية'),
        ('urgent', 'عاجلة'),
    ], string='الأولوية', default='normal')
    customer_id = fields.Many2one('utility.customer', 'العميل', index=True)
    account_id = fields.Many2one('utility.customer', 'الحساب', related='customer_id', store=True, index=True)
    meter_id = fields.Many2one('utility.meter', 'العداد', index=True)
    region_id = fields.Many2one('utility.region', 'المنطقة', related='customer_id.region_id', store=True)
    area_id = fields.Many2one('utility.region', 'المنطقة الفرعية', related='customer_id.area_id', store=True)
    zone_id = fields.Many2one('utility.region', 'المنطقة التفصيلية', domain="[('type', '=', 'zone')]")

    old_meter_id = fields.Many2one('utility.meter', 'العداد القديم')
    new_meter_id = fields.Many2one('utility.meter', 'العداد الجديد')
    description = fields.Text('الوصف', required=True)
    technician_id = fields.Many2one('res.users', 'الفني')
    team_id = fields.Many2one('utility.team', 'الفريق')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('approved', 'معتمد'),
        ('scheduled', 'مجدول'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغى'),
    ], string='الحالة', default='draft', tracking=True)
    findings = fields.Text('الملاحظات')
    meter_reading_before = fields.Float('قراءة العداد قبل')
    meter_reading_after = fields.Float('قراءة العداد بعد')
    seal_number_old = fields.Char('رقم الختم القديم')
    seal_number_new = fields.Char('رقم الختم الجديد')
    tamper_evidence = fields.Boolean('أدلة تلاعب')
    tamper_notes = fields.Text('ملاحظات التلاعب')
    cost_estimate = fields.Monetary('التكلفة التقديرية', currency_field='company_currency_id')
    actual_cost = fields.Monetary('التكلفة الفعلية', currency_field='company_currency_id')
    notes = fields.Text('ملاحظات')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='العملة')
    picking_ids = fields.One2many('stock.picking', compute='_compute_picking_ids', string='حركات المخزون')
    picking_count = fields.Integer(compute='_compute_picking_ids', string='عدد حركات المخزون')

    def _compute_picking_ids(self):
        for rec in self:
            pickings = self.env['stock.picking'].search([
                '|',
                ('origin', '=', rec.order_number),
                ('utility_operation_ref', 'ilike', f"SO:{rec.order_number}"),
            ])
            rec.picking_ids = pickings
            rec.picking_count = len(pickings)

    _sql_constraints = [
        ('unique_order_number_company', 'unique(order_number, company_id)',
         'رقم الأمر يجب أن يكون فريداً لكل شركة!'),
    ]

    def _check_state_transition(self, allowed_states):
        if self.state not in allowed_states:
            raise ValidationError(
                f'لا يمكن تنفيذ هذا الإجراء من الحالة "{self.state}". '
                f'الحالات المسموحة: {", ".join(allowed_states)}'
            )

    def action_approve(self):
        self._check_state_transition(['draft'])
        self.state = 'approved'

    def action_schedule(self):
        self._check_state_transition(['approved'])
        self.state = 'scheduled'
        self.date_scheduled = fields.Datetime.now()

    def action_start(self):
        self._check_state_transition(['scheduled'])
        self.state = 'in_progress'

    def action_complete(self):
        self._check_state_transition(['in_progress'])
        ctx = dict(self.env.context, skip_implicit_log=True, allow_log_update=True)

        if self.service_type == 'meter_replacement' and self.new_meter_id:
            op_ref = f"SO:{self.order_number}"
            if self.old_meter_id:
                self.old_meter_id.inventory_replace_meter(
                    new_meter=self.new_meter_id,
                    origin=self.order_number,
                    operation_ref=op_ref,
                    old_destination='inspection',
                )
                self.old_meter_id.with_context(ctx).write({'customer_id': False})
                self.env['utility.meter.log'].with_context(ctx)._create_log(
                    self.old_meter_id, 'removal',
                    _('رفع العداد عبر أمر خدمة %s: %s') % (self.order_number, self.description),
                    ref_record=self)
            else:
                self.new_meter_id.inventory_install_meter(
                    customer=self.customer_id,
                    origin=self.order_number,
                    operation_ref=f"{op_ref}:INSTALL",
                )

            self.new_meter_id.with_context(ctx).write({'customer_id': self.customer_id.id})
            self.env['utility.meter.log'].with_context(ctx)._create_log(
                self.new_meter_id, 'replacement',
                _('تركيب عداد عبر أمر خدمة %s: %s') % (self.order_number, self.description),
                ref_record=self)

        elif self.service_type == 'new_connection' and self.meter_id:
            op_ref = f"SO:{self.order_number}:INSTALL"
            self.meter_id.inventory_install_meter(
                customer=self.customer_id,
                origin=self.order_number,
                operation_ref=op_ref,
            )
            self.meter_id.with_context(ctx).write({'customer_id': self.customer_id.id})
            self.env['utility.meter.log'].with_context(ctx)._create_log(
                self.meter_id, 'install',
                _('تركيب عداد جديد عبر أمر خدمة %s: %s') % (self.order_number, self.description),
                ref_record=self)

        elif self.service_type == 'meter_removal' and self.meter_id:
            op_ref = f"SO:{self.order_number}:REMOVE"
            self.meter_id.inventory_remove_meter(
                origin=self.order_number,
                operation_ref=op_ref,
                destination='inspection',
            )
            self.meter_id.with_context(ctx).write({'customer_id': False})
            self.env['utility.meter.log'].with_context(ctx)._create_log(
                self.meter_id, 'removal',
                _('رفع العداد عبر أمر خدمة %s: %s') % (self.order_number, self.description),
                ref_record=self)

        elif self.service_type == 'disconnection' and self.customer_id:
            self.customer_id.with_context(
                lifecycle_service_order=True).action_disconnect(
                    reason=self.description, service_order=self)
            if self.meter_id:
                self.env['utility.meter.log'].with_context(ctx)._create_log(
                    self.meter_id, 'disconnection',
                    _('فصل العداد عبر أمر خدمة %s: %s') % (self.order_number, self.description),
                    ref_record=self)
        elif self.service_type == 'reconnection' and self.customer_id:
            self.customer_id.with_context(
                lifecycle_service_order=True).action_reconnect(
                    reason=self.description, service_order=self)
            if self.meter_id:
                self.env['utility.meter.log'].with_context(ctx)._create_log(
                    self.meter_id, 'reconnection',
                    _('إعادة خدمة العداد عبر أمر خدمة %s: %s') % (self.order_number, self.description),
                    ref_record=self)

        if self.meter_id and self.service_type not in ('meter_replacement', 'disconnection', 'reconnection', 'new_connection', 'meter_removal'):
            self.env['utility.meter.log'].with_context(ctx)._create_log(
                self.meter_id, 'service_order',
                _('أمر خدمة %s: %s') % (self.order_number, self.description),
                ref_record=self)

        self.state = 'completed'
        self.date_completed = fields.Datetime.now()

    def action_cancel(self):
        self._check_state_transition(['draft', 'approved', 'scheduled'])
        self.state = 'cancelled'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('order_number', _('جديد')) == _('جديد'):
                vals['order_number'] = self.env['ir.sequence'].next_by_code('utility.service.order') or _('جديد')
        return super().create(vals_list)

    @api.model
    def cron_detect_zero_consumption_meters(self, batch_limit=500):
        """الكشف التلقائي عن العدادات الخاملة أو المعطلة ذات الاستهلاك الصفري المتكرر.
        تبحث الدالة عن العدادات النشطة التي كانت قراءتها أو استهلاكها 0 لآخر 3 قراءات
        أو انقطعت قراءاتها، وتنشئ لها أمر تفتيش ميداني آلي."""
        Reading = self.env['utility.reading'].sudo()
        Meter = self.env['utility.meter'].sudo()

        active_meters = Meter.search([
            ('active', '=', True),
            ('customer_id', '!=', False),
            ('customer_id.state', '=', 'active'),
        ], limit=batch_limit)

        created_orders = self.env['utility.service.order']
        for meter in active_meters:
            open_inspection = self.search([
                ('meter_id', '=', meter.id),
                ('service_type', 'in', ('inspection', 'meter_test')),
                ('state', 'in', ('draft', 'approved', 'scheduled', 'in_progress')),
            ], limit=1)
            if open_inspection:
                continue

            readings = Reading.search([
                ('meter_id', '=', meter.id),
                ('state', 'in', ('approved', 'billed')),
            ], order='reading_date desc, id desc', limit=3)

            if len(readings) >= 3 and all(r.consumption == 0.0 for r in readings):
                order = self.create({
                    'service_type': 'inspection',
                    'priority': 'normal',
                    'customer_id': meter.customer_id.id,
                    'meter_id': meter.id,
                    'description': _('تفتيش آلي: العداد يسجل استهلاكاً صفرياً مستمراً لآخر %d قراءات متتالية. يرجى الفحص الميداني للتأكد من سلامة العداد.') % len(readings),
                    'state': 'draft',
                })
                created_orders |= order
        return len(created_orders)
