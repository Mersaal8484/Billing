import logging
from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityWorkflowService(models.AbstractModel):
    _name = 'utility.workflow.service'
    _description = 'مخدم إدارة ومحولات مسارات العمل الفترية'

    @api.model
    def _get_workflow_adapter(self):
        """الحصول على المحول النشط دون fallback صامت عند اختيار Temporal"""
        adapter_type = self.env['ir.config_parameter'].sudo().get_param('utility.workflow_adapter', 'local')
        if adapter_type == 'local':
            from ..adapters.workflow.local import LocalWorkflowAdapter
            return LocalWorkflowAdapter(self.env)
        elif adapter_type == 'temporal':
            from ..adapters.workflow.temporal import TemporalWorkflowAdapter
            return TemporalWorkflowAdapter(self.env)
        else:
            raise UserError(_("نوع محول مسارات العمل غير معروف: %s") % adapter_type)

    @api.model
    def trigger_reading_period_workflow(self, period_id):
        """بدء مسار عمل فترة القراءة عبر المحول النشط"""
        period = self.env['date.range'].browse(period_id).exists()
        if not period:
            raise ValidationError(_("الفترة المطلوبة غير موجودة."))
        adapter = self._get_workflow_adapter()
        return adapter.trigger_reading_period_workflow(period)

    @api.model
    def trigger_payment_period_workflow(self, payment_period_id):
        """بدء مسار عمل فترة التحصيل والسداد عبر المحول النشط"""
        payment_period = self.env['date.range'].browse(payment_period_id).exists()
        if not payment_period:
            raise ValidationError(_("فترة السداد المطلوبة غير موجودة."))
        adapter = self._get_workflow_adapter()
        return adapter.trigger_payment_period_workflow(payment_period)

    @api.model
    def execute_open_reading_window(self, period_id):
        """تطبيق فتح نافذة القراءة"""
        period = self.env['date.range'].browse(period_id)
        adapter = self._get_workflow_adapter()
        return adapter.execute_open_reading_window(period)

    @api.model
    def execute_close_reading_window(self, period_id):
        """تطبيق إغلاق نافذة القراءة"""
        period = self.env['date.range'].browse(period_id)
        adapter = self._get_workflow_adapter()
        return adapter.execute_close_reading_window(period)

    @api.model
    def execute_start_billing(self, period_id):
        """تطبيق الفوترة وتحويل القراءات"""
        period = self.env['date.range'].browse(period_id)
        adapter = self._get_workflow_adapter()
        return adapter.execute_start_billing(period)

    @api.model
    def execute_reconcile_and_close(self, period_id):
        """تطبيق نشاط المطابقة والإغلاق النهائي"""
        period = self.env['date.range'].browse(period_id)
        adapter = self._get_workflow_adapter()
        return adapter.execute_reconcile_and_close(period)

    @api.model
    def dispatch_batch_command(self, batch, payload_func, is_retry=False):
        """توجيه أمر معالجة الدفعة عبر المحول النشط بطريقة غير مكررة (Idempotent Batch Command)"""
        adapter = self._get_workflow_adapter()
        return adapter.dispatch_batch_command(batch, payload_func, is_retry=is_retry)
