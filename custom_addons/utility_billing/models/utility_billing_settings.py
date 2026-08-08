from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ─── الفوترة العامة ───────────────────────────────────────────────────────
    enable_auto_invoice_confirm = fields.Boolean(
        string='تأكيد الفواتير تلقائياً',
        config_parameter='utility.enable_auto_invoice_confirm',
        default=False)
    auto_generate_bills = fields.Boolean(
        string='توليد الفواتير تلقائياً من القراءات المعتمدة',
        config_parameter='utility.auto_generate_bills',
        default=True)
    billing_due_days = fields.Integer(
        string='أيام الاستحقاق (يوم)',
        config_parameter='utility.billing_due_days',
        default=30)
    billing_batch_size = fields.Integer(
        string='حجم دفعة تحديث حالة الفواتير',
        config_parameter='utility.billing_batch_size',
        default=1000,
        help='عدد الفواتير التي يعالجها كرون تحديث الحالة في كل تشغيل.')

    # ─── الغرامات ─────────────────────────────────────────────────────────────
    late_penalty_percentage = fields.Float(
        string='نسبة غرامة التأخير (%)',
        config_parameter='utility.late_penalty_percentage',
        default=1.5,
        help='النسبة المئوية من الرصيد المتبقي تُحتسب كغرامة يومية عند التأخر.')
    max_penalty_percentage = fields.Float(
        string='الحد الأقصى لإجمالي الغرامات (% من الفاتورة)',
        config_parameter='utility.max_penalty_percentage',
        default=30.0,
        help='لا تتجاوز الغرامات المتراكمة هذه النسبة من مبلغ الفاتورة الأصلي.')
    penalty_batch_size = fields.Integer(
        string='حجم دفعة احتساب الغرامات',
        config_parameter='utility.penalty_batch_size',
        default=500,
        help='عدد الفواتير التي يعالجها كرون الغرامات في كل تشغيل.')

    # ─── الفصل التلقائي ────────────────────────────────────────────────────────
    auto_disconnection_days = fields.Integer(
        string='أيام التأخر قبل الفصل التلقائي',
        config_parameter='utility.auto_disconnection_days',
        default=90,
        help='عدد الأيام من تاريخ الفاتورة المتأخرة قبل إنشاء أمر فصل آلي.')
    disconnection_batch_size = fields.Integer(
        string='حجم دفعة أوامر الفصل',
        config_parameter='utility.disconnection_batch_size',
        default=200,
        help='عدد أوامر الفصل التي يُنشئها الكرون في كل تشغيل.')

    # ─── التذكيرات والإشعارات ─────────────────────────────────────────────────
    reminder_batch_size = fields.Integer(
        string='حجم دفعة إرسال تذكيرات الفواتير',
        config_parameter='utility.reminder_batch_size',
        default=500,
        help='عدد الفواتير المتأخرة التي تُرسَل لها تذكيرات في كل تشغيل.')

    # ─── دفعات القراءات ───────────────────────────────────────────────────────
    reading_upload_batch_size = fields.Integer(
        string='حجم دفعة معالجة رفع القراءات',
        config_parameter='utility.reading_upload_batch_size',
        default=100,
        help='عدد القراءات التي تُعالَج في كل دورة من كرون رفع الدفعات.')
    reading_batch_cleanup_days = fields.Integer(
        string='الاحتفاظ بسجلات الدفعات (يوم)',
        config_parameter='utility.reading_batch_cleanup_days',
        default=30,
        help='عدد الأيام قبل حذف دفعات القراءات المكتملة من النظام.')
    billing_reading_batch_size = fields.Integer(
        string='حجم دفعة فوترة القراءات المعتمدة',
        config_parameter='utility.billing_reading_batch_size',
        default=200,
        help='عدد القراءات المعتمدة التي يفوترها الكرون في كل تشغيل.')

    # ─── العقود والفواتير المتكررة ────────────────────────────────────────────
    recurring_invoice_batch_size = fields.Integer(
        string='حجم دفعة الفواتير المتكررة',
        config_parameter='utility.recurring_invoice_batch_size',
        default=100,
        help='عدد العقود التي يُولّد لها الكرون فواتير متكررة في كل تشغيل.')
