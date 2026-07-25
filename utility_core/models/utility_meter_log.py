from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UtilityMeterLog(models.Model):
    _name = 'utility.meter.log'
    _description = 'سجل تاريخ العداد'
    _rec_name = 'name'
    _order = 'date desc, id desc'
    _check_company_auto = True

    _LOG_TYPE_ALIASES = {
        'install': 'installation',
    }

    name = fields.Char('المرجع', compute='_compute_name', store=True)
    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True, index=True,
        default=lambda self: self.env.company)
    meter_id = fields.Many2one(
        'utility.meter', string='العداد', required=True, index=True,
        ondelete='cascade', check_company=True)
    date = fields.Datetime(
        'التاريخ', default=fields.Datetime.now, required=True, index=True)
    user_id = fields.Many2one(
        'res.users', string='المستخدم', required=True,
        default=lambda self: self.env.user, index=True)
    log_type = fields.Selection([
        ('installation', 'تركيب'),
        ('replacement', 'استبدال'),
        ('removal', 'رفع'),
        ('settlement', 'تسوية قراءة'),
        ('service_order', 'أمر خدمة'),
        ('disconnection', 'فصل'),
        ('reconnection', 'إعادة خدمة'),
        ('movement', 'حركة مخزون'),
        ('status_change', 'تغيير حالة'),
        ('transfer', 'نقل بين المشتركين'),
        ('reading', 'قراءة'),
        ('tamper', 'تلاعب مثبت'),
        ('other', 'أخرى'),
    ], string='نوع الحدث', required=True, index=True)
    description = fields.Text('الوصف', required=True)
    ref_model = fields.Char('النموذج المصدر', index=True, readonly=True)
    ref_id = fields.Integer('معرف السجل المصدر', index=True, readonly=True)
    ref_name = fields.Char('مرجع المستند المصدر', readonly=True)
    customer_id = fields.Many2one(
        'utility.customer', string='حساب المشترك وقت الحدث',
        index=True, ondelete='set null', check_company=True)

    @api.depends('meter_id', 'log_type', 'date')
    def _compute_name(self):
        selection = dict(self._fields['log_type'].selection)
        for log in self:
            if log.meter_id and log.log_type:
                log.name = _('%s - %s') % (
                    selection.get(log.log_type, log.log_type),
                    log.meter_id.display_name,
                )
            else:
                log.name = _('سجل عداد جديد')

    @api.model
    def _normalize_log_type(self, log_type):
        """Translate legacy event keys emitted by existing modules."""
        return self._LOG_TYPE_ALIASES.get(log_type, log_type)

    @api.model_create_multi
    def create(self, vals_list):
        normalized_vals = []
        for incoming_vals in vals_list:
            vals = dict(incoming_vals)
            vals['log_type'] = self._normalize_log_type(vals.get('log_type'))
            meter = self.env['utility.meter'].browse(vals.get('meter_id')).exists()
            if meter:
                vals.setdefault('company_id', meter.company_id.id or self.env.company.id)
                vals.setdefault('customer_id', meter.customer_id.id or False)
            normalized_vals.append(vals)
        return super().create(normalized_vals)

    @api.model
    def _create_log(
        self, meter_id, log_type, description, ref_record=None,
        date=None, customer_id=None,
    ):
        """Create an immutable audit event without changing the source workflow."""
        meter = (
            meter_id.exists() if hasattr(meter_id, 'exists')
            else self.env['utility.meter'].browse(meter_id).exists()
        )
        if not meter:
            raise ValidationError(_('لا يمكن إنشاء سجل تاريخي دون عداد صحيح.'))

        customer = customer_id
        if not customer and ref_record:
            customer = getattr(ref_record, 'account_id', False) or getattr(
                ref_record, 'customer_id', False)
        if not customer:
            customer = meter.customer_id

        vals = {
            'meter_id': meter.id,
            'company_id': meter.company_id.id or self.env.company.id,
            'customer_id': customer.id if hasattr(customer, 'id') else customer or False,
            'log_type': self._normalize_log_type(log_type),
            'description': description,
            'date': date or fields.Datetime.now(),
            'user_id': self.env.user.id,
        }
        if ref_record:
            ref_record.ensure_one()
            vals.update({
                'ref_model': ref_record._name,
                'ref_id': ref_record.id,
                'ref_name': ref_record.display_name,
            })
        return self.create(vals)

    def action_open_source(self):
        """Open the business document that generated this audit event."""
        self.ensure_one()
        if not self.ref_model or not self.ref_id or self.ref_model not in self.env:
            raise UserError(_('المستند المصدر غير متاح أو تم حذفه.'))
        source = self.env[self.ref_model].browse(self.ref_id).exists()
        if not source:
            raise UserError(_('المستند المصدر غير موجود.'))
        source.check_access_rights('read')
        source.check_access_rule('read')
        return {
            'type': 'ir.actions.act_window',
            'name': self.ref_name or source.display_name,
            'res_model': self.ref_model,
            'res_id': source.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def write(self, vals):
        if not self.env.context.get('allow_log_update'):
            raise UserError(_(
                'لا يُسمح بتعديل سجل تاريخ العداد حفاظاً على موثوقية التدقيق.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get('allow_log_update'):
            raise UserError(_(
                'لا يُسمح بحذف سجل تاريخ العداد حفاظاً على موثوقية التدقيق.'))
        return super().unlink()
