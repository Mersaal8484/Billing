import logging
from odoo import fields, _
from odoo.exceptions import ValidationError
from .base import AbstractWorkflowAdapter

_logger = logging.getLogger(__name__)


class LocalWorkflowAdapter(AbstractWorkflowAdapter):
    """محول مسارات العمل المحلية (Local Workflow Adapter) للتطوير والاختبار الداخلي مع صندوق أوامر (Outbox Command Queue)"""

    def __init__(self, env):
        self.env = env

    def _record_command(self, period, action_type, summary, workflow_id, run_id, state='executed'):
        self.env['utility.workflow.command'].sudo().create({
            'name': f"CMD-{action_type.upper()}-{period.period_code}",
            'period_id': period.id,
            'action_type': action_type,
            'state': state,
            'result_summary': summary,
            'workflow_id': workflow_id,
            'workflow_run_id': run_id,
        })

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
        self._record_command(period, 'trigger_reading_workflow', f"بدء مسار عمل فترة القراءة {period.name}", workflow_id, run_id)
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
        self._record_command(payment_period, 'trigger_payment_workflow', f"بدء مسار عمل فترة التحصيل {payment_period.name}", workflow_id, run_id)
        return {
            'workflow_id': workflow_id,
            'workflow_run_id': run_id,
            'status': 'started',
            'period_code': payment_period.period_code,
            'adapter': 'local',
        }

    def execute_open_reading_window(self, period):
        period.action_open_reading()
        self._record_command(period, 'open_reading_window', _("تم فتح نافذة القراءة والرفع بنجاح."), period.workflow_id, period.workflow_run_id)
        return True

    def execute_close_reading_window(self, period):
        period.action_close_reading()
        self._record_command(period, 'close_reading_window', _("تم إغلاق نافذة القراءة بنجاح."), period.workflow_id, period.workflow_run_id)
        return True

    def execute_start_billing(self, period):
        period.action_start_billing()
        readings = self.env['utility.reading'].search([
            ('date_range_id', '=', period.id),
            ('state', '=', 'approved'),
            ('reading_purpose', '=', 'periodic')
        ])
        count = 0
        if readings:
            readings.action_generate_bills_batch()
            count = len(readings)
        self._record_command(period, 'start_billing', _("تم إرسال %d قراءة لطابور الفوترة.") % count, period.workflow_id, period.workflow_run_id)
        return count

    def execute_reconcile_and_close(self, period):
        period.action_close_period()
        self._record_command(period, 'reconcile_and_close', _("تمت المطابقة والإغلاق النهائي للفترة بنجاح."), period.workflow_id, period.workflow_run_id)
        return True
