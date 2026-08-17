import abc
import logging

_logger = logging.getLogger(__name__)


class AbstractWorkflowAdapter(abc.ABC):
    """
    معدل واجهة مسارات العمل المجرّدة (Generic Infrastructure Workflow Adapter Contract).
    يوفر واجهة قياسية محايدة للبنية التحتية يدعم التشغيل المحلي (Local) أو السحابي الموزع (Temporal).
    """

    @abc.abstractmethod
    def dispatch(self, workflow_type, reference_model, reference_id, payload=None, idempotency_key=None, priority=10):
        """
        توجيه أمر مسار العمل للبنية التحتية بطريقة غير مكررة (Idempotent Dispatch).
        
        :param workflow_type: رمز نوع مسار العمل الفني (e.g. 'reading_batch_process', 'open_reading_window')
        :param reference_model: اسم النموذج المرتبط بالأمر (e.g. 'utility.reading.batch', 'date.range')
        :param reference_id: المعرف الرقمي للسجل المستهدف
        :param payload: قاموس البيانات المدخلة القابلة للتسلسل (Dict)
        :param idempotency_key: مفتاح عدم التكرار الحتمي
        :param priority: أولوية التنفيذ (الرقم الأكبر ينفذ أولاً)
        :return: سجل utility.workflow.command أو استجابة المعالجة
        """
        pass

    @abc.abstractmethod
    def cancel(self, workflow_id, reason=None):
        """إلغاء مسار عمل قيد الانتظار."""
        pass

    @abc.abstractmethod
    def get_status(self, workflow_id):
        """الاستعلام عن حالة مسار العمل."""
        pass

    @abc.abstractmethod
    def execute_command(self, command):
        """تنفيذ أمر مسار عمل محدد محلياً (Local Execution Handler)."""
        pass

    # -------------------------------------------------------------------------
    # Backward Compatibility Forwarders
    # -------------------------------------------------------------------------
    def trigger_reading_period_workflow(self, period):
        return self.dispatch(
            workflow_type='trigger_reading_workflow',
            reference_model='date.range',
            reference_id=period.id,
            payload={'period_id': period.id, 'period_code': period.period_code},
            idempotency_key=f"TRIGGER_READING_WORKFLOW:{period.period_code}"
        )

    def trigger_payment_period_workflow(self, payment_period):
        return self.dispatch(
            workflow_type='trigger_payment_workflow',
            reference_model='date.range',
            reference_id=payment_period.id,
            payload={'period_id': payment_period.id, 'period_code': payment_period.period_code},
            idempotency_key=f"TRIGGER_PAYMENT_WORKFLOW:{payment_period.period_code}"
        )

    def execute_open_reading_window(self, period):
        return self.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=period.id,
            idempotency_key=f"OPEN_READING_WINDOW:{period.period_code}"
        )

    def execute_close_reading_window(self, period):
        return self.dispatch(
            workflow_type='close_reading_window',
            reference_model='date.range',
            reference_id=period.id,
            idempotency_key=f"CLOSE_READING_WINDOW:{period.period_code}"
        )

    def execute_start_billing(self, period):
        return self.dispatch(
            workflow_type='start_billing',
            reference_model='date.range',
            reference_id=period.id,
            idempotency_key=f"START_BILLING:{period.period_code}"
        )

    def execute_reconcile_and_close(self, period):
        return self.dispatch(
            workflow_type='reconcile_and_close',
            reference_model='date.range',
            reference_id=period.id,
            idempotency_key=f"RECONCILE_AND_CLOSE:{period.period_code}"
        )

    def dispatch_batch_command(self, batch, payload_func=None, is_retry=False):
        retry_suffix = f":RETRY:{batch.retry_count}" if (is_retry or getattr(batch, 'retry_count', 0) > 0) else ""
        idempotency_key = f"READING-BATCH:{batch.batch_uuid}{retry_suffix}"
        return self.dispatch(
            workflow_type='reading_batch_process',
            reference_model='utility.reading.batch',
            reference_id=batch.id,
            payload={'batch_id': batch.id, 'batch_uuid': batch.batch_uuid, 'retry_count': getattr(batch, 'retry_count', 0)},
            idempotency_key=idempotency_key,
        )
