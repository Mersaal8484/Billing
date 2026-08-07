import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UtilityTemporalService(models.AbstractModel):
    _name = 'utility.temporal.service'
    _description = 'مخدم التكامل مع موجه سير الأعمال Temporal Workflow'

    @api.model
    def trigger_reading_period_workflow(self, period_id):
        """بدء مسار عمل فترة القراءة في Temporal"""
        period = self.env['date.range'].browse(period_id).exists()
        if not period:
            raise ValidationError(_("الفترة المطلوبة غير موجودة."))

        workflow_id = f"reading-period-{period.period_code}"
        _logger.info("Temporal Workflow Triggered: %s for period %s", workflow_id, period.name)

        period.sudo().write({
            'workflow_id': workflow_id,
            'workflow_run_id': f"run-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"
        })
        return {
            'workflow_id': workflow_id,
            'status': 'started',
            'period_code': period.period_code,
        }

    @api.model
    def trigger_payment_period_workflow(self, payment_period_id):
        """بدء مسار عمل فترة السداد والتحصيل في Temporal"""
        period = self.env['date.range'].browse(payment_period_id).exists()
        if not period:
            raise ValidationError(_("فترة السداد المطلوبة غير موجودة."))

        workflow_id = f"payment-period-{period.period_code}"
        _logger.info("Temporal Payment Workflow Triggered: %s for period %s", workflow_id, period.name)

        period.sudo().write({
            'workflow_id': workflow_id,
            'workflow_run_id': f"run-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"
        })
        return {
            'workflow_id': workflow_id,
            'status': 'started',
            'period_code': period.period_code,
        }

    @api.model
    def execute_activity_open_reading_window(self, period_id):
        """Temporal Activity: فتح نافذة القراءة"""
        period = self.env['date.range'].browse(period_id)
        period.action_open_reading()
        return True

    @api.model
    def execute_activity_close_reading_window(self, period_id):
        """Temporal Activity: إغلاق نافذة القراءة"""
        period = self.env['date.range'].browse(period_id)
        period.action_close_reading()
        return True

    @api.model
    def execute_activity_start_billing(self, period_id):
        """Temporal Activity: بدء تحويل القراءات إلى فواتير"""
        period = self.env['date.range'].browse(period_id)
        period.action_start_billing()
        
        readings = self.env['utility.reading'].search([
            ('date_range_id', '=', period.id),
            ('state', '=', 'approved'),
            ('reading_purpose', '=', 'periodic')
        ])
        if readings:
            readings.action_generate_bills_batch()
        return len(readings)

    @api.model
    def execute_activity_reconcile_and_close(self, period_id):
        """Temporal Activity: المطابقة والإغلاق النهائي"""
        period = self.env['date.range'].browse(period_id)
        period.action_close_period()
        return True
