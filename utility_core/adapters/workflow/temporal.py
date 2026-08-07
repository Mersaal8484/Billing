import logging
from odoo import _
from odoo.exceptions import UserError
from .base import AbstractWorkflowAdapter

_logger = logging.getLogger(__name__)


class TemporalWorkflowAdapter(AbstractWorkflowAdapter):
    """
    محول مسارات العمل لبيئة الإنتاج عبر خدمة Temporal (Temporal Workflow Adapter - V1 Placeholder Contract).
    ملاحظة: هذا المحول حالياً يُجسّد هيكلية العقد المتبادل (Interface Contract) وفي انتظار ربط مكتبة Temporal SDK الرسمية.
    """

    def __init__(self, env):
        self.env = env
        self.target_host = env['ir.config_parameter'].sudo().get_param('utility.temporal_target_host', '')
        self.namespace = env['ir.config_parameter'].sudo().get_param('utility.temporal_namespace', 'default')

        # فحص إعدادات الاتصال بالخدمة ومنع silent fallback
        if not self.target_host:
            raise UserError(_("خطأ في إعدادات البنية التحتية: خادم Temporal غير محدد (utility.temporal_target_host)."))

    def trigger_reading_period_workflow(self, period):
        _logger.info("Executing Temporal Workflow trigger for period %s at %s", period.name, self.target_host)
        return True

    def trigger_payment_period_workflow(self, payment_period):
        _logger.info("Executing Temporal Workflow trigger for payment period %s at %s", payment_period.name, self.target_host)
        return True

    def execute_open_reading_window(self, period):
        _logger.info("Executing Temporal Workflow open reading window for period %s", period.name)
        return period.action_open_reading()

    def execute_close_reading_window(self, period):
        _logger.info("Executing Temporal Workflow close reading window for period %s", period.name)
        return period.action_close_reading()

    def execute_start_billing(self, period):
        _logger.info("Executing Temporal Workflow start billing for period %s", period.name)
        return period.action_start_billing()

    def execute_reconcile_and_close(self, period):
        _logger.info("Executing Temporal Workflow reconcile and close for period %s", period.name)
        return period.action_close_period()

    def dispatch_batch_command(self, batch, payload_func, is_retry=False):
        _logger.info("Executing Temporal Batch Workflow Command for batch %s", batch.name)
        return payload_func()
