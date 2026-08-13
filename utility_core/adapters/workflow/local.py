import json
import logging
from psycopg2 import OperationalError
from odoo import fields, _
from odoo.exceptions import ValidationError
from .base import AbstractWorkflowAdapter

_logger = logging.getLogger(__name__)


class LocalWorkflowAdapter(AbstractWorkflowAdapter):
    """محول مسارات العمل المحلية (Local Workflow Adapter) مع طابور أوامر متين (Durable Local Outbox Queue & Idempotency)"""

    def __init__(self, env):
        self.env = env

    def _dispatch_command(self, period, action_type, payload_func, summary_func, payload_data=None):
        """
        تنفيذ أمر عبر نمط صندوق الرسائل المنشورة مع الادعاء الذري (Atomic Claim & Durable Local Outbox Dispatcher):
        1. إنشاء/جلب أمر بمفتاح عدم التكرار (Idempotency Key).
        2. حجز السجل ذريًا بواسطة FOR UPDATE NOWAIT مع معالجة 55P03 فقط عند التنافس.
        3. التحقق المنطقي من الحالة (مكفولة ألا تُعاد معالجة الأوامر في حالتي processing أو executed).
        4. تحويل الحالة ذريًا من pending/failed إلى processing وتسجيل وقت البدء وزيادة عدد المحاولات.
        5. تنفيذ الإجراء المستهدف (Business Function) مرة واحدة فقط.
        6. عند النجاح: تحويل الحالة إلى executed وتسجيل وقت الإكمال والنتيجة.
        7. عند الفشل: تحويل الحالة إلى failed وتسجيل رسالة الخطأ ثم إعادة رفع الاستثناء.
        """
        idempotency_key = f"{action_type.upper()}:{period.period_code}"
        cmd_model = self.env['utility.workflow.command'].sudo()
        payload_str = json.dumps(payload_data, ensure_ascii=False) if payload_data else False

        existing = cmd_model.search([('idempotency_key', '=', idempotency_key)], limit=1)
        cmd = existing or cmd_model.create({
            'name': f"CMD-{action_type.upper()}-{period.period_code}",
            'idempotency_key': idempotency_key,
            'period_id': period.id,
            'action_type': action_type,
            'state': 'pending',
            'workflow_id': period.workflow_id,
            'workflow_run_id': period.workflow_run_id,
            'payload_json': payload_str,
        })

        try:
            self.env.cr.execute(
                "SELECT id FROM utility_workflow_command WHERE id = %s FOR UPDATE NOWAIT",
                (cmd.id,)
            )
        except OperationalError as e:
            pgcode = getattr(e, 'pgcode', None)
            if pgcode == '55P03':
                _logger.info("Command %s (key: %s) is currently locked by another worker (55P03). Skipping.", cmd.id, idempotency_key)
                return cmd.result_summary
            raise

        cmd.refresh()
        if cmd.state == 'executed':
            _logger.info("Command already executed for key %s (UUID: %s)", idempotency_key, cmd.command_uuid)
            return cmd.result_summary
        if cmd.state == 'processing':
            _logger.info("Command %s already in processing state. Skipping re-execution.", cmd.id)
            return cmd.result_summary
        if cmd.state == 'failed' and cmd.attempt_count >= cmd.max_attempts:
            raise ValidationError(_("تجاوز أمر مسار العمل الحد الأقصى للمحاولات المسموحة (%d).") % cmd.max_attempts)

        cmd.write({
            'state': 'processing',
            'started_at': fields.Datetime.now(),
            'attempt_count': cmd.attempt_count + 1,
        })

        try:
            res = payload_func()
            summary = summary_func(res) if callable(summary_func) else summary_func
            cmd.write({
                'state': 'executed',
                'completed_at': fields.Datetime.now(),
                'result_summary': summary,
            })
            return res
        except Exception as e:
            cmd.write({
                'state': 'failed',
                'error_message': str(e),
            })
            _logger.error("Command execution failed for %s: %s", idempotency_key, str(e))
            raise

    def trigger_reading_period_workflow(self, period):
        if not period or not period.exists():
            raise ValidationError(_("فترة القراءة غير موجودة."))

        workflow_id = f"local-reading-{period.period_code}"
        run_id = f"run-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"

        _logger.info("Local Workflow Triggered: %s for reading period %s", workflow_id, period.name)

        def _action():
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

        return self._dispatch_command(
            period, 'trigger_reading_workflow',
            _action,
            lambda r: f"بدء مسار عمل فترة القراءة {period.name} (WF: {workflow_id})",
            payload_data={'period_id': period.id, 'period_code': period.period_code}
        )

    def trigger_payment_period_workflow(self, payment_period):
        if not payment_period or not payment_period.exists():
            raise ValidationError(_("فترة السداد غير موجودة."))

        workflow_id = f"local-payment-{payment_period.period_code}"
        run_id = f"run-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"

        _logger.info("Local Workflow Triggered: %s for payment period %s", workflow_id, payment_period.name)

        def _action():
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

        return self._dispatch_command(
            payment_period, 'trigger_payment_workflow',
            _action,
            lambda r: f"بدء مسار عمل فترة التحصيل {payment_period.name} (WF: {workflow_id})",
            payload_data={'period_id': payment_period.id, 'period_code': payment_period.period_code}
        )

    def execute_open_reading_window(self, period):
        return self._dispatch_command(
            period, 'open_reading_window',
            lambda: period.action_open_reading() or True,
            _("تم فتح نافذة القراءة والرفع بنجاح.")
        )

    def execute_close_reading_window(self, period):
        return self._dispatch_command(
            period, 'close_reading_window',
            lambda: period.action_close_reading() or True,
            _("تم إغلاق نافذة القراءة بنجاح.")
        )

    def execute_start_billing(self, period):
        def _action():
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
            return count

        return self._dispatch_command(
            period, 'start_billing',
            _action,
            lambda count: _("تم تحويل %d قراءة معتمدة إلى فواتير بنجاح.") % count
        )

    def execute_reconcile_and_close(self, period):
        return self._dispatch_command(
            period, 'reconcile_and_close',
            lambda: period.action_close_period() or True,
            _("تمت المطابقة والإغلاق النهائي للفترة بنجاح.")
        )

    def dispatch_batch_command(self, batch, payload_func, is_retry=False):
        """تنفيذ أمر معالجة دفعة القراءات عبر مفتاح عدم التكرار (Idempotency Key) READING-BATCH:{batch_uuid} مع الادعاء الذري"""
        retry_suffix = f":RETRY:{batch.retry_count}" if (is_retry or getattr(batch, 'retry_count', 0) > 0) else ""
        idempotency_key = f"READING-BATCH:{batch.batch_uuid}{retry_suffix}"
        cmd_model = self.env['utility.workflow.command'].sudo()
        existing = cmd_model.search([('idempotency_key', '=', idempotency_key)], limit=1)

        cmd = existing or cmd_model.create({
            'name': f"CMD-BATCH-{batch.name}" + (f"-R{batch.retry_count}" if retry_suffix else ""),
            'idempotency_key': idempotency_key,
            'action_type': 'reading_batch',
            'period_id': batch.date_range_id.id if batch.date_range_id else False,
            'res_model': 'utility.reading.batch',
            'res_id': batch.id,
            'state': 'pending',
            'payload_json': json.dumps({'batch_id': batch.id, 'batch_uuid': batch.batch_uuid, 'retry_count': getattr(batch, 'retry_count', 0)}, ensure_ascii=False),
        })

        try:
            self.env.cr.execute(
                "SELECT id FROM utility_workflow_command WHERE id = %s FOR UPDATE NOWAIT",
                (cmd.id,)
            )
        except OperationalError as e:
            pgcode = getattr(e, 'pgcode', None)
            if pgcode == '55P03':
                _logger.info("Batch Command %s is currently locked by another worker (55P03). Skipping.", cmd.id)
                return cmd.result_summary
            raise

        cmd.refresh()
        if cmd.state == 'executed':
            _logger.info("Batch Command already executed for key %s (UUID: %s)", idempotency_key, cmd.command_uuid)
            return cmd.result_summary
        if cmd.state == 'processing':
            _logger.info("Batch Command %s already in processing state. Skipping re-execution.", cmd.id)
            return cmd.result_summary
        if cmd.state == 'failed' and cmd.attempt_count >= cmd.max_attempts:
            raise ValidationError(_("تجاوز أمر الدفعة الحد الأقصى للمحاولات المسموحة (%d).") % cmd.max_attempts)

        cmd.write({
            'state': 'processing',
            'started_at': fields.Datetime.now(),
            'attempt_count': cmd.attempt_count + 1,
        })

        try:
            res = payload_func()
            summary = f"Batch {batch.name} processed: {res.get('success_count', 0)} success, {res.get('error_count', 0)} errors" if isinstance(res, dict) else str(res)
            cmd.write({
                'state': 'executed',
                'completed_at': fields.Datetime.now(),
                'result_summary': summary,
            })
            return res
        except Exception as e:
            cmd.write({
                'state': 'failed',
                'error_message': str(e),
            })
            raise
