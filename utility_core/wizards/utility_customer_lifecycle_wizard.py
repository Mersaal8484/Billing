from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityCustomerLifecycleWizard(models.TransientModel):
    _name = 'utility.customer.lifecycle.wizard'
    _description = 'إجراء دورة حياة الحساب الكهربائي'

    customer_id = fields.Many2one('utility.customer', required=True, readonly=True)
    current_state = fields.Selection(related='customer_id.state', readonly=True)
    current_meter_id = fields.Many2one(
        'utility.meter', related='customer_id.meter_id', readonly=True)
    action_type = fields.Selection([
        ('suspend', 'تعليق الحساب'),
        ('reactivate', 'إعادة التفعيل'),
        ('disconnect', 'فصل الخدمة'),
        ('reconnect', 'إعادة التوصيل'),
        ('close', 'إغلاق الحساب'),
    ], required=True, readonly=True)
    reason = fields.Char('السبب', required=True)
    effective_date = fields.Datetime('تاريخ السريان', default=fields.Datetime.now, required=True)
    notes = fields.Text('ملاحظات')
    administrative_override = fields.Boolean('اعتماد إداري استثنائي')
    final_reading = fields.Float(
        'القراءة الختامية', default=False, digits=(12, 3),
        help='تُسجل على تخصيص العداد الحالي عند الإغلاق. تلقائية إذا وُجدت قراءة مسجلة على العداد.')
    require_field_removal = fields.Boolean(
        'طلب إزالة العداد ميدانياً',
        help='حدد هذا الخيار إذا كان لا بد من إصدار أمر خدمة مكتمل لإزالة العداد من الموقع.')

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        customer = self.env['utility.customer'].browse(
            self.env.context.get('active_id')).exists()
        if customer:
            values['customer_id'] = customer.id
            values['action_type'] = self.env.context.get('lifecycle_action')
        return values

    def action_confirm(self):
        self.ensure_one()
        customer = self.customer_id
        context = dict(self.env.context)
        if self.administrative_override:
            if not self.env.user.has_group('utility_core.group_utility_admin'):
                raise ValidationError(_('الاعتماد الإداري الاستثنائي متاح لمدير النظام فقط.'))
            context['lifecycle_override'] = True
        customer = customer.with_context(context)
        if self.action_type == 'suspend':
            customer.action_suspend(self.reason, self.effective_date, self.notes)
        elif self.action_type == 'reactivate':
            customer.action_reactivate(self.reason, self.notes)
        service_order = getattr(self, 'service_order_id', False)
        if self.action_type == 'disconnect':
            customer.action_disconnect(
                self.reason, self.effective_date, self.notes, service_order)
        elif self.action_type == 'reconnect':
            customer.action_reconnect(self.reason, self.notes, service_order)
        elif self.action_type == 'close':
            customer.action_close(
                self.reason, self.effective_date, self.notes,
                final_reading=self.final_reading,
                require_field_removal=self.require_field_removal,
                service_order=service_order)
        return {'type': 'ir.actions.act_window_close'}
