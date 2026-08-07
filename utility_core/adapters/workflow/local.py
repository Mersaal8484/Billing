import logging
from odoo import fields, _
from odoo.exceptions import ValidationError
from .base import AbstractWorkflowAdapter

_logger = logging.getLogger(__name__)


class LocalWorkflowAdapter(AbstractWorkflowAdapter):
    """محول مسارات العمل المحلية (Local Workflow Adapter) للتطوير والاختبار الداخلي"""

    def __init__(self, env):
        self.env = env

    def trigger_reading_period_workflow(self, period):
        if not period or not period.exists():
            raise ValidationError(_("فترة القراءة غير موجودة."))

        workflow_id = f"local-reading-{period.period_code}"
        run_id = f"run-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"

        _logger.info("Local Workflow Triggered: %s for reading period %s", workflow_id, period.name)

        period.sudo().write({
            'workflow_id': workflow_id,
            'workflow_run_id': run_id,
        })
        return {
            'workflow_id': workflow_id,
            'workflow_run_id': run_id,
            'status': 'started',
            'period_code': period.period_code,
            'adapter': 'local',
        }

    def trigger_payment_period_workflow(self, payment_period):
        if not payment_period or not payment_period.exists():
            raise ValidationError(_("فترة السداد غير موجودة."))

        workflow_id = f"local-payment-{payment_period.period_code}"
        run_id = f"run-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"

        _logger.info("Local Workflow Triggered: %s for payment period %s", workflow_id, payment_period.name)

        payment_period.sudo().write({
            'workflow_id': workflow_id,
            'workflow_run_id': run_id,
        })
        return {
            'workflow_id': workflow_id,
            'workflow_run_id': run_id,
            'status': 'started',
            'period_code': payment_period.period_code,
            'adapter': 'local',
        }

    def execute_open_reading_window(self, period):
        period.action_open_reading()
        return True

    def execute_close_reading_window(self, period):
        period.action_close_reading()
        return True

    def execute_start_billing(self, period):
        period.action_start_billing()
        readings = self.env['utility.reading'].search([
            ('date_range_id', '=', period.id),
            ('state', '=', 'approved'),
            ('reading_purpose', '=', 'periodic')
        ])
        if readings:
            readings.action_generate_bills_batch()
        return len(readings)

    def execute_reconcile_and_close(self, period):
        period.action_close_period()
        return True
