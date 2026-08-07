import logging
from odoo import api, models, _
from odoo.exceptions import ValidationError
from ..adapters.workflow.local import LocalWorkflowAdapter

_logger = logging.getLogger(__name__)


class UtilityWorkflowService(models.AbstractModel):
    _name = 'utility.workflow.service'
    _description = 'مخدم إدارة ومحولات مسارات العمل الفترية'

    @api.model
    def _get_workflow_adapter(self):
        """الحصول على المحول النشط (Default: LocalWorkflowAdapter)"""
        # يمكن مستقبلاً قراءة الخيار من ir.config_parameter لإرجاع TemporalWorkflowAdapter للإنتاج
        adapter_type = self.env['ir.config_parameter'].sudo().get_param('utility.workflow_adapter', 'local')
        if adapter_type == 'local':
            return LocalWorkflowAdapter(self.env)
        else:
            # Fallback to local adapter for standard execution
            return LocalWorkflowAdapter(self.env)

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
        """بدء مسار عمل فترة السداد والتحصيل عبر المحول النشط"""
        period = self.env['date.range'].browse(payment_period_id).exists()
        if not period:
            raise ValidationError(_("فترة السداد المطلوبة غير موجودة."))
        adapter = self._get_workflow_adapter()
        return adapter.trigger_payment_period_workflow(period)

    @api.model
    def execute_activity_open_reading_window(self, period_id):
        """تطبيق نشاط فتح نافذة القراءة"""
        period = self.env['date.range'].browse(period_id)
        adapter = self._get_workflow_adapter()
        return adapter.execute_open_reading_window(period)

    @api.model
    def execute_activity_close_reading_window(self, period_id):
        """تطبيق نشاط إغلاق نافذة القراءة"""
        period = self.env['date.range'].browse(period_id)
        adapter = self._get_workflow_adapter()
        return adapter.execute_close_reading_window(period)

    @api.model
    def execute_activity_start_billing(self, period_id):
        """تطبيق نشاط بدء الفوترة"""
        period = self.env['date.range'].browse(period_id)
        adapter = self._get_workflow_adapter()
        return adapter.execute_start_billing(period)

    @api.model
    def execute_activity_reconcile_and_close(self, period_id):
        """تطبيق نشاط المطابقة والإغلاق النهائي"""
        period = self.env['date.range'].browse(period_id)
        adapter = self._get_workflow_adapter()
        return adapter.execute_reconcile_and_close(period)

    @api.model
    def dispatch_batch_command(self, batch, payload_func):
        """توجيه أمر معالجة الدفعة عبر المحول النشط بطريقة غير مكررة (Idempotent Batch Command)"""
        adapter = self._get_workflow_adapter()
        return adapter.dispatch_batch_command(batch, payload_func)
