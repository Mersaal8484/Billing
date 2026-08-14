import json
import logging
from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityWorkflowService(models.AbstractModel):
    _name = 'utility.workflow.service'
    _description = 'مخدم وسيط إدارة ومحولات مسارات العمل (Central Workflow Service & Registry)'

    # =========================================================================
    # Workflow Type Registry
    # =========================================================================
    WORKFLOW_REGISTRY = {
        'reading_batch_process': {
            'model': 'utility.reading.batch',
            'desc': 'معالجة دفعات قراءات العدادات',
            'service_model': 'utility.reading.batch.service',
            'service_method': 'process_batch',
        },
        'open_reading_window': {
            'model': 'date.range',
            'desc': 'فتح نافذة رفع القراءات',
            'service_model': 'date.range',
            'service_method': 'action_open_reading',
        },
        'close_reading_window': {
            'model': 'date.range',
            'desc': 'إغلاق نافذة رفع القراءات',
            'service_model': 'date.range',
            'service_method': 'action_close_reading',
        },
        'start_billing': {
            'model': 'date.range',
            'desc': 'بدء الفوترة الدورية للفترة',
            'service_model': 'date.range',
            'service_method': 'action_start_billing',
        },
        'reconcile_and_close': {
            'model': 'date.range',
            'desc': 'المطابقة والإغلاق النهائي للفترة',
            'service_model': 'date.range',
            'service_method': 'action_close_period',
        },
        'trigger_reading_workflow': {
            'model': 'date.range',
            'desc': 'بدء مسار عمل فترة القراءة',
            'service_model': 'date.range',
            'service_method': 'action_open_reading',
        },
        'trigger_payment_workflow': {
            'model': 'date.range',
            'desc': 'بدء مسار عمل فترة السداد والتحصيل',
            'service_model': 'date.range',
            'service_method': 'action_open_reading',
        },
    }

    @api.model
    def _get_workflow_adapter(self):
        """الحصول على المحول النشط دون fallback صامت عند اختيار Temporal"""
        adapter_type = self.env['ir.config_parameter'].sudo().get_param('utility.workflow_adapter', 'local')
        if adapter_type == 'local':
            from ..adapters.workflow.local import LocalWorkflowAdapter
            return LocalWorkflowAdapter(self.env)
        elif adapter_type == 'temporal':
            from ..adapters.workflow.temporal import TemporalWorkflowAdapter
            if not getattr(TemporalWorkflowAdapter, 'PRODUCTION_READY', False):
                raise UserError(_("محول Temporal Workflow غير جاهز للإنتاج حالياً (Placeholder Contract). يُرجى استخدام Local Odoo Outbox."))
            return TemporalWorkflowAdapter(self.env)
        else:
            raise UserError(_("نوع محول مسارات العمل غير معروف: %s") % adapter_type)

    @api.model
    def dispatch(self, workflow_type, reference_model, reference_id, payload=None, idempotency_key=None, priority=10):
        """
        المدخل المركزي المعتمد لإطلاق أوامر مسارات العمل:
        1. التحقق من سلامة نوع المسار والنموذج المرتبط.
        2. التحقق من وجود السجل المستهدف في قاعدة البيانات.
        3. تمرير الأمر إلى المحول النشط مع ضمان عدم التكرار.
        """
        record = self.env[reference_model].browse(reference_id).exists()
        if not record:
            raise ValidationError(_("السجل المرجعي المستهدف (%s, ID: %s) غير موجود في النظام.") % (reference_model, reference_id))

        if not idempotency_key:
            idempotency_key = f"{workflow_type.upper()}:{reference_model}:{reference_id}"

        adapter = self._get_workflow_adapter()
        return adapter.dispatch(
            workflow_type=workflow_type,
            reference_model=reference_model,
            reference_id=reference_id,
            payload=payload,
            idempotency_key=idempotency_key,
            priority=priority,
        )

    @api.model
    def _execute_workflow_handler(self, workflow_type, reference_model, reference_id, payload_json=None):
        """
        استدعاء خدمة الأعمال القابلة لإعادة الاستخدام (Reusable Business Service):
        يتم استدعاء نفس الدالة سواء كان المشغل محلياً اليوم أو نشاط Temporal غداً.
        """
        reg = self.WORKFLOW_REGISTRY.get(workflow_type)
        payload = json.loads(payload_json) if payload_json else {}

        if reg:
            target_model = reg.get('service_model') or reference_model
            method_name = reg.get('service_method')
            target = self.env[target_model]

            if hasattr(target, method_name):
                method = getattr(target, method_name)
                if target_model == reference_model:
                    rec = target.browse(reference_id)
                    return method(rec) if method.__code__.co_argcount > 1 else method()
                else:
                    return method(reference_id)
            else:
                _logger.warning("Method [%s] not found on [%s] for workflow [%s].", method_name, target_model, workflow_type)

        # Fallback to direct model action if matching method exists
        rec = self.env[reference_model].browse(reference_id)
        if hasattr(rec, f"action_{workflow_type}"):
            return getattr(rec, f"action_{workflow_type}")()

        raise ValidationError(_("لا توجد خدمة أعمال مسجلة لمعالجة نوع مسار العمل: %s") % workflow_type)

    # -------------------------------------------------------------------------
    # Backward Compatibility Forwarders
    # -------------------------------------------------------------------------
    @api.model
    def trigger_reading_period_workflow(self, period_id):
        period = self.env['date.range'].browse(period_id).exists()
        if not period:
            raise ValidationError(_("الفترة المطلوبة غير موجودة."))
        return self.dispatch(
            workflow_type='trigger_reading_workflow',
            reference_model='date.range',
            reference_id=period.id,
            payload={'period_id': period.id, 'period_code': period.period_code},
            idempotency_key=f"TRIGGER_READING_WORKFLOW:{period.period_code}"
        )

    @api.model
    def trigger_payment_period_workflow(self, payment_period_id):
        payment_period = self.env['date.range'].browse(payment_period_id).exists()
        if not payment_period:
            raise ValidationError(_("فترة السداد المطلوبة غير موجودة."))
        return self.dispatch(
            workflow_type='trigger_payment_workflow',
            reference_model='date.range',
            reference_id=payment_period.id,
            payload={'period_id': payment_period.id, 'period_code': payment_period.period_code},
            idempotency_key=f"TRIGGER_PAYMENT_WORKFLOW:{payment_period.period_code}"
        )

    @api.model
    def execute_open_reading_window(self, period_id):
        period = self.env['date.range'].browse(period_id).exists()
        return self.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=period.id,
            idempotency_key=f"OPEN_READING_WINDOW:{period.period_code}"
        )

    @api.model
    def execute_close_reading_window(self, period_id):
        period = self.env['date.range'].browse(period_id).exists()
        return self.dispatch(
            workflow_type='close_reading_window',
            reference_model='date.range',
            reference_id=period.id,
            idempotency_key=f"CLOSE_READING_WINDOW:{period.period_code}"
        )

    @api.model
    def execute_start_billing(self, period_id):
        period = self.env['date.range'].browse(period_id).exists()
        return self.dispatch(
            workflow_type='start_billing',
            reference_model='date.range',
            reference_id=period.id,
            idempotency_key=f"START_BILLING:{period.period_code}"
        )

    @api.model
    def execute_reconcile_and_close(self, period_id):
        period = self.env['date.range'].browse(period_id).exists()
        return self.dispatch(
            workflow_type='reconcile_and_close',
            reference_model='date.range',
            reference_id=period.id,
            idempotency_key=f"RECONCILE_AND_CLOSE:{period.period_code}"
        )

    @api.model
    def dispatch_batch_command(self, batch, payload_func=None, is_retry=False):
        adapter = self._get_workflow_adapter()
        return adapter.dispatch_batch_command(batch, payload_func=payload_func, is_retry=is_retry)
