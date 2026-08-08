import uuid
from odoo import fields, models


class UtilityWorkflowCommand(models.Model):
    _name = 'utility.workflow.command'
    _description = 'سجل وطابور أوامر مسارات العمل (Local Outbox Command Queue)'
    _order = 'create_date desc, id desc'

    name = fields.Char('رمز الأمر', required=True, index=True)
    command_uuid = fields.Char(
        string='رمز المعرف الفريد (Command UUID)',
        required=True,
        copy=False,
        index=True,
        default=lambda self: str(uuid.uuid4())
    )
    idempotency_key = fields.Char(
        string='مفتاح عدم التكرار (Idempotency Key)',
        required=True,
        copy=False,
        index=True
    )
    period_id = fields.Many2one('date.range', string='الفترة', required=False, ondelete='cascade', index=True)
    action_type = fields.Char('نوع الإجراء', required=True, default='general', index=True)

    # ===== مراجع مرنة لربط أي نموذج (Generic Model Reference) =====
    res_model = fields.Char('الموديل المرتبط (Model Name)', index=True)
    res_id = fields.Many2oneReference('معرف السجل المرتبط (Record ID)', model_field='res_model', index=True)

    state = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('processing', 'قيد المعالجة'),
        ('executed', 'تم التنفيذ'),
        ('failed', 'فشل'),
    ], default='pending', required=True, index=True)

    attempt_count = fields.Integer('عدد المحاولات', default=0, required=True)
    max_attempts = fields.Integer('الحد الأقصى للمحاولات', default=3, required=True)

    scheduled_at = fields.Datetime('تاريخ التجدول', default=fields.Datetime.now, required=True)
    started_at = fields.Datetime('تاريخ بدء التنفيذ')
    completed_at = fields.Datetime('تاريخ إكمال التنفيذ')

    result_summary = fields.Text('ملخص النتيجة')
    error_message = fields.Text('رسالة الخطأ')

    workflow_id = fields.Char('مرجع مسار العمل (Workflow Ref)')
    workflow_run_id = fields.Char('مرجع تشغيل مسار العمل (Workflow Run Ref)')
    payload_json = fields.Text('بيانات الطلب (Payload JSON)')

    _sql_constraints = [
        ('unique_idempotency_key', 'unique(idempotency_key)', 'مفتاح عدم التكرار (Idempotency Key) يجب أن يكون فريداً لكل أمر!'),
        ('unique_workflow_id', 'unique(workflow_id)', 'مرجع مسار العمل (Workflow ID) يجب أن يكون فريداً عند تحديده!'),
    ]
