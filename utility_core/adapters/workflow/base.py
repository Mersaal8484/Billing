import abc
import logging

_logger = logging.getLogger(__name__)


class AbstractWorkflowAdapter(abc.ABC):
    """معدل واجهة مسارات العمل المجرّدة (Workflow Adapter Base)"""

    @abc.abstractmethod
    def trigger_reading_period_workflow(self, period):
        """بدء مسار عمل فترة القراءة"""
        pass

    @abc.abstractmethod
    def trigger_payment_period_workflow(self, payment_period):
        """بدء مسار عمل فترة السداد والتحصيل"""
        pass

    @abc.abstractmethod
    def execute_open_reading_window(self, period):
        """تطبيق فتح نافذة القراءة"""
        pass

    @abc.abstractmethod
    def execute_close_reading_window(self, period):
        """تطبيق إغلاق نافذة القراءة"""
        pass

    @abc.abstractmethod
    def execute_start_billing(self, period):
        """تطبيق بدء الفوترة وتحويل القراءات"""
        pass

    @abc.abstractmethod
    def execute_reconcile_and_close(self, period):
        """تطبيق المطابقة والإغلاق النهائي للفترة"""
        pass
