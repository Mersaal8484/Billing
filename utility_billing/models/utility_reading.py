import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UtilityReading(models.Model):
    _inherit = 'utility.reading'

    batch_id = fields.Many2one('utility.reading.batch', 'الدفعة', readonly=True, index=True)

    def _check_billing_period_mutation(self, vals=None):
        """Prevent ordinary reading changes after the billing period is closed."""
        if (self.env.context.get('allow_billing_adjustment')
                or self.env.context.get('_bypass_reading_protection')):
            return
        if self.filtered(lambda reading: reading.date_range_id.state in ('closed', 'locked')):
            raise ValidationError(_(
                'لا يمكن تعديل قراءة مرتبطة بفترة مغلقة أو مقفلة. '
                'استخدم مسار تعديل الفوترة المعتمد.'))

    @api.model_create_multi
    def create(self, vals_list):
        period_ids = [vals.get('date_range_id') for vals in vals_list if vals.get('date_range_id')]
        if period_ids and not self.env.context.get('allow_billing_adjustment'):
            closed = self.env['date.range'].search([
                ('id', 'in', period_ids), ('state', 'in', ('closed', 'locked')),
            ], limit=1)
            if closed:
                raise ValidationError(_(
                    'لا يمكن إنشاء قراءة في الفترة المغلقة أو المقفلة [%s].') % closed.name)
        return super().create(vals_list)

    def write(self, vals):
        self._check_billing_period_mutation(vals)
        return super().write(vals)

    def _queue_approved_billable_readings(self):
        """Move newly approved periodic billable readings to the billing queue.

        This is deliberately centralized on the inherited reading model so every
        approval entry point (form buttons, review console, and bulk approval)
        follows the same workflow. Non-billable readings remain ``approved``.
        """
        readings = self.filtered(
            lambda reading: reading.state == 'approved'
            and reading.reading_purpose == 'periodic'
            and reading.date_range_id
            and reading.is_billable
            and (
                reading.reading_category == 'customer'
                or (
                    reading.reading_category == 'transformer'
                    and reading.is_private_transformer
                )
            )
        )
        if readings:
            readings.with_context(_bypass_reading_protection=True).write({
                'state': 'queued',
                'billing_error': False,
            })
        return readings

    def action_approve(self):
        """Approve readings and immediately enqueue billable periodic readings."""
        result = super().action_approve()
        self._queue_approved_billable_readings()
        return result

    def _get_billing_period_type(self):
        self.ensure_one()
        recurring_type = (
            self.account_id._get_effective_billing_period()
            if self.account_id else False
        )
        return {'bi_monthly': 'biweekly'}.get(recurring_type, recurring_type)

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
        return period

    def _get_unbilled_closing_components(self):
        """Return approved replacement closings eligible for this periodic bill."""
        self.ensure_one()
        last_periodic = self.search([
            ('account_id', '=', self.account_id.id),
            ('reading_purpose', '=', 'periodic'),
            ('state', '=', 'billed'),
            ('reading_date', '<', self.reading_date),
            ('id', '!=', self.id),
        ], order='reading_date desc, id desc', limit=1)
        domain = [
            ('company_id', '=', self.company_id.id),
            ('account_id', '=', self.account_id.id),
            ('reading_purpose', '=', 'replacement_closing'),
            ('state', '=', 'approved'),
            ('billing_anchor_id', '=', False),
            ('included_sale_order_id', '=', False),
            ('reading_date', '<=', self.reading_date),
        ]
        if last_periodic:
            domain.append(('reading_date', '>', last_periodic.reading_date))
        return self.search(domain, order='reading_date, id')

    def _lock_closing_components(self, closings):
        """Lock still-unassigned closing readings against concurrent billing workers."""
        if not closings:
            return closings
        self.env.flush_all()
        self.env.cr.execute("""
            SELECT id
              FROM utility_reading
             WHERE id IN %s
               AND billing_anchor_id IS NULL
               AND included_sale_order_id IS NULL
             FOR UPDATE
        """, [tuple(closings.ids)])
        locked_ids = [row[0] for row in self.env.cr.fetchall()]
        return self.browse(locked_ids)

    def _prepare_component_vals(self, order, readings):
        """Prepare immutable billing snapshots for all consumption segments."""
        return [{
            'sale_order_id': order.id,
            'reading_id': reading.id,
            'account_id': reading.account_id.id,
            'meter_id': reading.meter_id.id,
            'period_start': reading.previous_reading_date,
            'period_end': reading.reading_date,
            'previous_reading': reading.previous_reading,
            'current_reading': reading.reading_value,
            'meter_multiplier': reading.meter_multiplier or 1.0,
            'consumption': reading.consumption,
            'company_id': reading.company_id.id,
        } for reading in readings]

    def _action_generate_periodic_bill(self):
        """Create one bill from a periodic reading and pending closing segments."""
        self.ensure_one()
        if self.reading_purpose != 'periodic':
            raise ValidationError(_('لا يمكن إنشاء فاتورة إلا من قراءة دورية.'))
        if self.state not in ('approved', 'queued'):
            raise ValidationError(_('يجب اعتماد القراءة الدورية قبل إنشاء الفاتورة.'))
        if not self.date_range_id:
            period = self._get_current_billing_date_range()
            if not period:
                raise ValidationError(_('يجب تحديد فترة القراءة الدورية قبل الفوترة.'))
            self.with_context(_bypass_reading_protection=True).write({'date_range_id': period.id})
        
        if self.date_range_id.state in ('closed', 'locked'):
            raise ValidationError(_('فترة القراءة (%s) في حالة (%s) وتمنع إنشاء فواتير جديدة.') % (self.date_range_id.name, self.date_range_id.state))

        existing = self.env['sale.order'].search([
            ('reading_id', '=', self.id), ('state', '!=', 'cancel')], limit=1)
        if existing:
            raise ValidationError(_('تم إنشاء فاتورة لهذه القراءة مسبقاً.'))

        closings = self._lock_closing_components(
            self._get_unbilled_closing_components())
        total_consumption = self.consumption + sum(closings.mapped('consumption'))
        template = self.account_id.contract_template_id
        order = self.env['sale.order'].create({
            'partner_id': self.account_id.partner_id.id or self.env.company.partner_id.id,
            'customer_id': self.account_id.id,
            'meter_id': self.meter_id.id,
            'reading_id': self.id,
            'date_range_id': self.date_range_id.id,
            'date_order': fields.Datetime.now(),
            'period_start': self.date_range_id.date_start or (
                self.previous_reading_date.date() if self.previous_reading_date else fields.Date.today()),
            'period_end': self.date_range_id.date_end or (
                self.reading_date.date() if self.reading_date else fields.Date.today()),
            'previous_reading': self.previous_reading,
            'current_reading': self.reading_value,
            'consumption': total_consumption,
            'contract_template_id': template.id if template else False,
        })
        all_components = closings | self
        self.env['utility.bill.reading.component'].create(
            self._prepare_component_vals(order, all_components))
        if closings:
            closings.with_context(_bypass_reading_protection=True).write({
                'billing_anchor_id': self.id,
                'included_sale_order_id': order.id,
                'state': 'billed',
            })
        self.with_context(_bypass_reading_protection=True).write({
            'included_sale_order_id': order.id,
        })
        if template:
            order._calculate_amounts()
        order.action_confirm()
        invoices = order._create_invoices()
        invoices.action_post()
        if self.image_asset_id and self.image_asset_id.original_attachment_id:
            order.attachment_id = self.image_asset_id.original_attachment_id
        elif self.attachment_id:
            order.attachment_id = self.attachment_id
        self.with_context(_bypass_reading_protection=True).write({
            'state': 'billed', 'billing_error': False,
        })
        self.account_id.write({
            'last_invoice_date': fields.Datetime.now(),
            'last_invoice_reading': self.reading_value,
            'last_reading_date': self.reading_date,
            'last_reading_value': self.reading_value,
        })
        return {
            'type': 'ir.actions.act_window', 'res_model': 'sale.order',
            'res_id': order.id, 'views': [(False, 'form')],
        }

    def action_generate_bill(self):
        return self._action_generate_periodic_bill()

    def action_generate_bills_batch(self):
        readings = self.filtered(lambda r: r.reading_purpose == 'periodic' and r.date_range_id and r.state == 'approved' and (
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
            ('reading_purpose', '=', 'periodic'),
            ('date_range_id', '!=', False),
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
        readings = self.search([('state', '=', 'queued'), ('reading_purpose', '=', 'periodic')], limit=batch_size)
        if not readings:
            return

        success_count = 0
        error_count = 0
        for reading in readings:
            try:
                with self.env.cr.savepoint():
                    reading.action_generate_bill()
                success_count += 1
            except Exception as exc:
                reading.write({
                    'state': 'error',
                    'billing_error': str(exc),
                })
                _logger.exception(
                    'Bill generation failed for reading %s',
                    reading.display_name,
                )
                error_count += 1

        _logger.info(
            'Batch Billing: processed %d readings (%d success, %d errors)',
            len(readings), success_count, error_count
        )
