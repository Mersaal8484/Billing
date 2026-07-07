from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityReading(models.Model):
    _inherit = 'utility.reading'

    batch_id = fields.Many2one('utility.reading.batch', 'الدفعة', readonly=True, index=True)

    def _get_billing_period_type(self):
        self.ensure_one()
        template = self.account_id.contract_template_id if self.account_id else False
        recurring_type = template.recurring_rule_type if template else False
        return {
            'bi_monthly': 'biweekly',
        }.get(recurring_type or 'monthly', recurring_type or 'monthly')

    def _get_current_billing_date_range(self):
        self.ensure_one()
        billing_period = self._get_billing_period_type()
        domain = [
            ('is_current_period', '=', True),
            ('work_type', '=', 'readings'),
        ]
        if billing_period:
            domain.append(('billing_period', '=', billing_period))
        period = self.env['date.range'].search(domain, limit=1)
        if not period:
            period = self.env['date.range'].search([
                ('is_current_period', '=', True),
                ('work_type', '=', 'readings'),
            ], limit=1)
        return period

    def action_generate_bill(self):
        """إنشاء أمر بيع (فاتورة) من القراءة المعتمدة وربط المرفق رسمياً"""
        self.ensure_one()
        is_billable = (self.reading_category == 'customer' or (self.reading_category == 'transformer' and self.is_private_transformer))
        if not is_billable:
            raise ValidationError('إنشاء الفواتير متاح فقط لقراءات المشتركين والمحولات الخاصة!')
        if self.state != 'approved':
            raise ValidationError('يجب الموافقة على القراءة أولاً قبل إنشاء الفاتورة!')
        existing_order = self.env['sale.order'].search([
            ('reading_id', '=', self.id),
            ('state', '!=', 'cancel'),
        ], limit=1)
        if existing_order:
            raise ValidationError('تم إنشاء فاتورة لهذه القراءة مسبقاً!')
        if not self.date_range_id:
            period = self._get_current_billing_date_range()
            if not period:
                raise ValidationError(_(
                    'يجب تحديد فترة الفوترة على القراءة قبل إنشاء الفاتورة، '
                    'أو تعيين فترة نشطة حالية لنوع العمل "قراءات".'
                ))
            self.write({'date_range_id': period.id})
        template = self.account_id.contract_template_id
        consumption = self.consumption
        order = self.env['sale.order'].create({
            'partner_id': self.account_id.partner_id.id if self.account_id.partner_id else self.env.company.partner_id.id,
            'customer_id': self.account_id.id,
            'meter_id': self.meter_id.id,
            'reading_id': self.id,
            'date_range_id': self.date_range_id.id,
            'date_order': fields.Datetime.now(),
            'period_start': self.previous_reading_date.date() if self.previous_reading_date else fields.Date.today(),
            'period_end': self.reading_date.date() if self.reading_date else fields.Date.today(),
            'previous_reading': self.previous_reading,
            'current_reading': self.reading_value,
            'consumption': consumption,
            'contract_template_id': template.id if template else False,
        })
        if template:
            order._calculate_amounts()

        # تأكيد أمر البيع وإنشاء الفاتورة المحاسبية وترحيلها تلقائياً
        order.action_confirm()
        invoices = order._create_invoices()
        for inv in invoices:
            inv.action_post()

        if self.meter_image:
            attach = self.env['ir.attachment'].create({
                'name': f'invoice_meter_{order.name or self.reading_id}.png',
                'type': 'binary',
                'datas': self.meter_image,
                'res_model': 'sale.order',
                'res_id': order.id,
            })
            order.attachment_id = attach.id
            self.attachment_id = attach.id

        self.write({'state': 'billed', 'billing_error': False})
        if self.account_id:
            self.account_id.write({
                'last_invoice_date': fields.Datetime.now(),
                'last_invoice_reading': self.reading_value,
                'last_reading_date': self.reading_date,
                'last_reading_value': self.reading_value,
            })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': order.id,
            'views': [(False, 'form')],
        }

    def action_generate_bills_batch(self):
        readings = self.filtered(lambda r: r.state == 'approved' and (
            r.reading_category == 'customer' or
            (r.reading_category == 'transformer' and r.is_private_transformer)
        ))
        if not readings:
            raise ValidationError('لا توجد قراءات معتمدة قابلة للفوترة!')
        readings.write({'state': 'queued', 'billing_error': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'طابور الفوترة',
                'message': f'تم إرسال {len(readings)} قراءة إلى طابور الفوترة. سيتم معالجتها تلقائياً.',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def cron_queue_approved_readings(self):
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'utility.billing_queue_batch_size', 1000))
        readings = self.search([
            ('state', '=', 'approved'),
            '|',
            ('reading_category', '=', 'customer'),
            '&',
            ('reading_category', '=', 'transformer'),
            ('is_private_transformer', '=', True),
        ], limit=batch_size, order='reading_date asc, id asc')
        if readings:
            readings.write({'state': 'queued', 'billing_error': False})
        return len(readings)
    def action_requeue(self):
        for r in self:
            if r.state != 'error':
                raise ValidationError('يمكن إعادة المحاولة فقط للقراءات التي بها خطأ!')
            r.write({'state': 'queued', 'billing_error': False})

    @api.model
    def _cron_generate_bills(self):
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'utility.billing_batch_size', 500))
        readings = self.search([('state', '=', 'queued')], limit=batch_size)
        if not readings:
            return

        success_count = 0
        error_count = 0
        for reading in readings:
            try:
                reading.action_generate_bill()
                self.env.cr.commit()
                success_count += 1
            except Exception as e:
                self.env.cr.rollback()
                reading.write({
                    'state': 'error',
                    'billing_error': str(e),
                })
                self.env.cr.commit()
                error_count += 1

        _logger = __import__('logging').getLogger(__name__)
        _logger.info(
            'Batch Billing: processed %d readings (%d success, %d errors)',
            len(readings), success_count, error_count
        )
