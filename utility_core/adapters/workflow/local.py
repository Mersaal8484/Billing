import json
import logging
import traceback
from psycopg2 import OperationalError, IntegrityError

from odoo import fields, _
from odoo.exceptions import UserError, ValidationError
from .base import AbstractWorkflowAdapter

_logger = logging.getLogger(__name__)


class LocalWorkflowAdapter(AbstractWorkflowAdapter):
    """
    محول مسارات العمل المحلية (Local Workflow Adapter):
    طابور أوامر متين في قاعدة البيانات (Durable PostgreSQL Outbox)
    مع الادعاء الذري (Atomic Claiming) وعدم التكرار الحتمي (Deterministic Idempotency).
    """

    def __init__(self, env):
        self.env = env

    def dispatch(self, workflow_type, reference_model, reference_id, payload=None, idempotency_key=None, priority=10):
        """
        توجيه وحفظ أمر مسار العمل ذرياً في جدول utility.workflow.command.
        """
        if not idempotency_key:
            idempotency_key = f"{workflow_type.upper()}:{reference_model}:{reference_id}"

        cmd_model = self.env['utility.workflow.command'].sudo()
        payload_str = json.dumps(payload, ensure_ascii=False) if isinstance(payload, (dict, list)) else (payload or False)

        existing = cmd_model.search([('idempotency_key', '=', idempotency_key)], limit=1)
        if existing:
            cmd = existing
        else:
            try:
                with self.env.cr.savepoint():
                    cmd = cmd_model.create({
                        'name': f"CMD-{workflow_type.upper()}-{reference_id}",
                        'idempotency_key': idempotency_key,
                        'workflow_type': workflow_type,
                        'reference_model': reference_model,
                        'reference_id': reference_id,
                        'state': 'pending',
                        'backend': 'local',
                        'priority': priority,
                        'payload_json': payload_str,
                    })
            except IntegrityError as e:
                pgcode = getattr(e, 'pgcode', None)
                if pgcode != '23505':
                    raise
                cmd = cmd_model.search([('idempotency_key', '=', idempotency_key)], limit=1)
                if not cmd:
                    raise

        if not cmd:
            raise ValidationError(_("فشل إنشاء أو استرجاع أمر مسار العمل."))

        return cmd

    def cancel(self, workflow_id, reason=None):
        """إلغاء أمر مسار العمل بواسطة المعرف أو الكود."""
        cmd = self.env['utility.workflow.command'].sudo().search([
            '|', ('idempotency_key', '=', workflow_id),
            '|', ('command_uuid', '=', workflow_id),
            ('id', '=', int(workflow_id) if str(workflow_id).isdigit() else 0),
        ], limit=1)
        if not cmd:
            raise ValidationError(_("أمر مسار العمل (%s) غير موجود.") % workflow_id)
        return cmd.action_cancel(reason=reason)

    def get_status(self, workflow_id):
        """الاستعلام عن حالة ومخرجات أمر مسار العمل."""
        cmd = self.env['utility.workflow.command'].sudo().search([
            '|', ('idempotency_key', '=', workflow_id),
            '|', ('command_uuid', '=', workflow_id),
            ('id', '=', int(workflow_id) if str(workflow_id).isdigit() else 0),
        ], limit=1)
        if not cmd:
            return {'status': 'not_found', 'workflow_id': workflow_id}
        return {
            'status': cmd.state,
            'workflow_id': cmd.command_uuid,
            'idempotency_key': cmd.idempotency_key,
            'attempt_count': cmd.attempt_count,
            'started_at': cmd.started_at,
            'completed_at': cmd.completed_at,
            'result': cmd.result_summary,
            'last_error': cmd.last_error,
        }

    def execute_command(self, command, payload_func=None, summary_func=None):
        """
        تنفيذ أمر مسار العمل محلياً مع الادعاء الذري وحفظ النتائج:
        1. حجز الأمر بقفل قاعدة البيانات (FOR UPDATE NOWAIT / SKIP LOCKED).
        2. تشغيل خدمة الأعمال المخصصة داخل Savepoint مستقل.
        3. تسجيل النجاح أو الفشل والتراجع الزمني.
        """
        cmd = command.sudo() if hasattr(command, 'sudo') else self.env['utility.workflow.command'].sudo().browse(command)
        if not cmd.exists():
            return {'status': 'not_found'}

        # Claim the command atomically
        claimed = cmd.action_claim()
        if not claimed:
            _logger.info("Command [%s] could not be claimed (state=%s, locked or already executed).", cmd.name, cmd.state)
            return {'status': 'skipped', 'result': cmd.result_summary}

        try:
            with self.env.cr.savepoint():
                if callable(payload_func):
                    res = payload_func()
                else:
                    wf_service = self.env['utility.workflow.service']
                    res = wf_service._execute_workflow_handler(cmd.workflow_type, cmd.reference_model, cmd.reference_id, cmd.payload_json)

                summary = summary_func(res) if callable(summary_func) else (
                    summary_func if summary_func is not None else (
                        json.dumps(res, ensure_ascii=False) if isinstance(res, (dict, list)) else str(res)
                    )
                )
                cmd.action_complete(result=summary)
                return {'status': 'success', 'result': res, 'summary': summary}
        except (UserError, ValidationError) as biz_err:
            tb = traceback.format_exc()
            cmd.action_fail(error=str(biz_err), error_category='business', error_details=tb)
            _logger.warning("Business error executing command [%s]: %s", cmd.name, biz_err)
            return {'status': 'failed', 'error': str(biz_err), 'category': 'business'}
        except OperationalError as op_err:
            tb = traceback.format_exc()
            cmd.action_fail(error=str(op_err), error_category='transient', error_details=tb)
            _logger.error("Transient DB operational error executing command [%s]: %s", cmd.name, op_err)
            return {'status': 'failed', 'error': str(op_err), 'category': 'transient'}
        except Exception as exc:
            tb = traceback.format_exc()
            cmd.action_fail(error=str(exc), error_category='unexpected', error_details=tb)
            _logger.exception("Unexpected exception executing command [%s]: %s", cmd.name, exc)
            return {'status': 'failed', 'error': str(exc), 'category': 'unexpected'}

    # -------------------------------------------------------------------------
    # Backward Compatibility Internal Dispatchers
    # -------------------------------------------------------------------------
    def _dispatch_command(self, period, action_type, payload_func, summary_func, payload_data=None):
        """دعم التوافقية العكسية للاختبارات السابقة."""
        idempotency_key = f"{action_type.upper()}:{period.period_code}"
        cmd = self.dispatch(
            workflow_type=action_type,
            reference_model='date.range',
            reference_id=period.id,
            payload=payload_data,
            idempotency_key=idempotency_key,
        )

        cmd.invalidate_recordset(['state', 'result_summary'])
        if cmd.state in ('completed', 'executed'):
            return cmd.result_summary
        if cmd.state == 'processing':
            return cmd.result_summary

        exec_res = self.execute_command(cmd, payload_func=payload_func, summary_func=summary_func)
        if exec_res.get('status') == 'failed':
            raise ValidationError(exec_res.get('error'))
        return exec_res.get('result') or exec_res.get('summary')

    def dispatch_batch_command(self, batch, payload_func, is_retry=False):
        """دعم التوافقية العكسية لدفعات القراءة."""
        retry_suffix = f":RETRY:{batch.retry_count}" if (is_retry or getattr(batch, 'retry_count', 0) > 0) else ""
        idempotency_key = f"READING-BATCH:{batch.batch_uuid}{retry_suffix}"

        cmd = self.dispatch(
            workflow_type='reading_batch_process',
            reference_model='utility.reading.batch',
            reference_id=batch.id,
            payload={'batch_id': batch.id, 'batch_uuid': batch.batch_uuid, 'retry_count': getattr(batch, 'retry_count', 0)},
            idempotency_key=idempotency_key,
        )

        cmd.invalidate_recordset(['state', 'result_summary'])
        if cmd.state in ('completed', 'executed'):
            return cmd.result_summary
        if cmd.state == 'processing':
            return cmd.result_summary

        def _summary_cb(res):
            if isinstance(res, dict):
                return f"Batch {batch.name} processed: {res.get('success_count', 0)} success, {res.get('error_count', 0)} errors"
            return str(res)

        exec_res = self.execute_command(cmd, payload_func=payload_func, summary_func=_summary_cb)
        if exec_res.get('status') == 'failed':
            raise ValidationError(exec_res.get('error'))
        return exec_res.get('result') or exec_res.get('summary')
