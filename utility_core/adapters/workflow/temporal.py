import logging
from odoo import _
from odoo.exceptions import UserError
from .base import AbstractWorkflowAdapter

_logger = logging.getLogger(__name__)


class TemporalWorkflowAdapter(AbstractWorkflowAdapter):
    """
    محول مسارات العمل لبيئة الإنتاج عبر خدمة Temporal (Temporal Workflow Adapter - Production Target Contract).
    ملاحظة: هذا المحول حالياً يُجسّد هيكلية العقد المتبادل (Interface Contract) وفي انتظار ربط مكتبة Temporal SDK الرسمية في مرحلة الإنتاج.
    """
    PRODUCTION_READY = False

    def __init__(self, env):
        self.env = env
        self.target_host = env['ir.config_parameter'].sudo().get_param('utility.temporal_target_host', '')
        self.namespace = env['ir.config_parameter'].sudo().get_param('utility.temporal_namespace', 'default')

        # فحص إعدادات الاتصال بالخدمة ومنع silent fallback
        if not self.target_host:
            raise UserError(_("خطأ في إعدادات البنية التحتية: خادم Temporal غير محدد (utility.temporal_target_host)."))

    def dispatch(self, workflow_type, reference_model, reference_id, payload=None, idempotency_key=None, priority=10):
        if not self.PRODUCTION_READY:
            raise UserError(_("محول Temporal Workflow قيد التجهيز لمرحلة الإنتاج (Temporal SDK not attached yet). يُرجى استخدام Local Odoo Outbox."))
        _logger.info("Dispatching to Temporal Workflow: type=%s, ref=%s:%s, key=%s", workflow_type, reference_model, reference_id, idempotency_key)
        return True

    def cancel(self, workflow_id, reason=None):
        if not self.PRODUCTION_READY:
            raise UserError(_("محول Temporal Workflow قيد التجهيز لمرحلة الإنتاج."))
        _logger.info("Cancelling Temporal Workflow: id=%s", workflow_id)
        return True

    def get_status(self, workflow_id):
        if not self.PRODUCTION_READY:
            raise UserError(_("محول Temporal Workflow قيد التجهيز لمرحلة الإنتاج."))
        return {'status': 'pending', 'workflow_id': workflow_id}

    def execute_command(self, command):
        if not self.PRODUCTION_READY:
            raise UserError(_("محول Temporal Workflow قيد التجهيز لمرحلة الإنتاج."))
        return {'status': 'failed', 'error': 'Temporal adapter does not execute local commands.'}
