from odoo import fields, models


class UtilityWorkflowCommand(models.Model):
    _name = 'utility.workflow.command'
    _description = 'سجل أوامر تنفيذ مسارات العمل (Local Outbox Command)'
    _order = 'create_date desc, id desc'

    name = fields.Char('رمز الأمر', required=True, index=True)
    period_id = fields.Many2one('date.range', string='الفترة', required=True, ondelete='cascade', index=True)
    action_type = fields.Char('نوع الإجراء', required=True, index=True)
    state = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('executed', 'تم التنفيذ'),
        ('failed', 'فشل'),
    ], default='executed', required=True, index=True)
    result_summary = fields.Text('ملخص النتيجة')
    workflow_id = fields.Char('مرجع مسار العمل')
    workflow_run_id = fields.Char('مرجع تشغيل مسار العمل')
