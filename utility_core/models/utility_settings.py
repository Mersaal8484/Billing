from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    legacy_single_phase_meter_model_id = fields.Many2one(
        'utility.meter.model', related='company_id.legacy_single_phase_meter_model_id',
        readonly=False, string='موديل العداد القديم — أحادي الطور',
        domain=[('phase', '=', 'single')])
    legacy_three_phase_meter_model_id = fields.Many2one(
        'utility.meter.model', related='company_id.legacy_three_phase_meter_model_id',
        readonly=False, string='موديل العداد القديم — ثلاثي الطور',
        domain=[('phase', '=', 'three')])

    pos_epson_printer_ip = fields.Char(
        string='عنوان IP طابعة Epson',
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='العملة',
        readonly=True,
    )

    group_display_incoterm = fields.Boolean(
        string='شروط التجارة الدولية (Incoterms)',
        implied_group='account.group_delivery_invoice_address',
    )
    default_picking_policy = fields.Selection([
        ('direct', 'تسليم كل منتج عند توفره'),
        ('one', 'تسليم جميع المنتجات دفعة واحدة'),
    ], string='سياسة الشحن والتوصيل', default='direct', default_model='sale.order')
    use_security_lead = fields.Boolean(
        string='مهلة الأمان للتسليم',
        config_parameter='sale.use_security_lead',
    )
    security_lead = fields.Float(
        string='مهلة أمان التسليم بالأيام',
        config_parameter='sale.security_lead',
    )
    group_stock_packaging = fields.Boolean(
        string='التعبئة والتغليف للمخزون',
        implied_group='product.group_stock_packaging',
    )
    group_discount_per_so_line = fields.Boolean(
        string='خصومات بنود أوامر البيع',
        implied_group='product.group_discount_per_so_line',
    )
    module_delivery = fields.Boolean(
        string='طرق التوصيل والشحن',
    )

    # --- Meter Reading ---
    meter_review_required = fields.Boolean(
        string='مطلوب مراجعة صورة العداد',
        config_parameter='utility.meter_review_required',
        default=True)
    meter_image_mandatory = fields.Boolean(
        string='صورة العداد إلزامية',
        config_parameter='utility.meter_image_mandatory',
        default=False)
    meter_reading_validation = fields.Selection([
        ('none', 'بدون تحقق'),
        ('consumption_diff', 'التحقق من فرق الاستهلاك'),
        ('image_review', 'مراجعة الصورة'),
        ('both', 'كلاهما'),
    ], string='نوع التحقق من القراءة',
       config_parameter='utility.meter_reading_validation',
       default='both')

    # --- Transformer ---
    max_transformer_loss_tolerance = fields.Float(
        string='نسبة الفاقد المسموح في المحولات (%)',
        config_parameter='utility.max_transformer_loss_tolerance',
        default=10.0)

    # --- Consumption Alerts ---
    high_consumption_threshold = fields.Float(
        string='حد الاستهلاك العالي (kWh)',
        config_parameter='utility.high_consumption_threshold',
        default=10000.0)
    consumption_variation_alert_percentage = fields.Float(
        string='نسبة التغير المنبهة للاستهلاك (%)',
        config_parameter='utility.consumption_variation_alert_percentage',
        default=50.0)

    # --- Auto Pay ---
    max_auto_pay_retries = fields.Integer(
        string='الحد الأقصى لإعادة محاولة الدفع',
        config_parameter='utility.max_auto_pay_retries',
        default=3)

    # --- SMS / Notifications ---
    stock_move_sms_validation = fields.Boolean(
        string='تأكيد رسائل SMS لحركات المخزون',
        config_parameter='utility.stock_move_sms_validation',
        default=False)
    stock_sms_confirmation_template_id = fields.Many2one(
        'sms.template',
        string='قالب رسائل SMS لتأكيد المخزون',
        config_parameter='utility.stock_sms_confirmation_template_id')
    send_sms_on_invoice = fields.Boolean(
        string='إرسال SMS عند إنشاء الفاتورة',
        config_parameter='utility.send_sms_on_invoice',
        default=False)
    send_sms_on_payment = fields.Boolean(
        string='إرسال SMS عند الدفع',
        config_parameter='utility.send_sms_on_payment',
        default=False)
    send_sms_on_overdue = fields.Boolean(
        string='إرسال SMS عند تأخر الفاتورة',
        config_parameter='utility.send_sms_on_overdue',
        default=False)

    # --- Accounting ---
    fine_account_id = fields.Many2one(
        'account.account',
        related='company_id.fine_account_id',
        readonly=False,
        string='حساب إيرادات الغرامات')
    discount_account_id = fields.Many2one(
        'account.account',
        related='company_id.discount_account_id',
        readonly=False,
        string='حساب الخصومات / الإعفاءات')
    deposit_account_id = fields.Many2one(
        'account.account',
        related='company_id.deposit_account_id',
        readonly=False,
        string='حساب التأمينات')
    settlement_account_id = fields.Many2one(
        'account.account',
        related='company_id.settlement_account_id',
        readonly=False,
        string='حساب التسويات المالية')
    writeoff_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.writeoff_journal_id',
        readonly=False,
        string='يومية الإعفاءات')
    deposit_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.deposit_journal_id',
        readonly=False,
        string='يومية التأمينات والودائع')
    settlement_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.settlement_journal_id',
        readonly=False,
        string='يومية التسويات')
    opening_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.opening_journal_id',
        readonly=False,
        string='يومية الأرصدة الافتتاحية')
    penalty_product_id = fields.Many2one(
        'product.product',
        related='company_id.penalty_product_id',
        readonly=False,
        string='منتج الغرامات')
    mu_allim_product_id = fields.Many2one(
        'product.product',
        related='company_id.mu_allim_product_id',
        readonly=False,
        string='منتج المعلم')
    cleaning_product_id = fields.Many2one(
        'product.product',
        related='company_id.cleaning_product_id',
        readonly=False,
        string='منتج النظافة')
    local_fee_product_id = fields.Many2one(
        'product.product',
        related='company_id.local_fee_product_id',
        readonly=False,
        string='منتج المجالس المحلية')
    writeoff_account_id = fields.Many2one(
        'account.account',
        related='company_id.writeoff_account_id',
        readonly=False,
        string='حساب الإعفاءات')
    collection_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.collection_journal_id',
        readonly=False,
        string='يومية التحصيل الافتراضية')
    sales_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.sales_journal_id',
        readonly=False,
        string='يومية مبيعات الكهرباء')
    electricity_income_account_id = fields.Many2one(
        'account.account',
        related='company_id.electricity_income_account_id',
        readonly=False,
        string='حساب إيرادات مبيعات الكهرباء')
    electricity_product_id = fields.Many2one(
        'product.product',
        related='company_id.electricity_product_id',
        readonly=False,
        string='منتج طاقة الكهرباء الرئيسي')
    discount_product_id = fields.Many2one(
        'product.product',
        related='company_id.discount_product_id',
        readonly=False,
        string='منتج الخصم والإعفاءات')
    private_transformer_fee_product_id = fields.Many2one(
        'product.product',
        related='company_id.private_transformer_fee_product_id',
        readonly=False,
        string='منتج رسوم المحول الخاص')

    # --- Infrastructure Settings (إعدادات البنية التحتية — مسارات العمل والوسائط) ---
    workflow_backend = fields.Selection([
        ('local', 'Local Odoo (In-Process Outbox)'),
        ('temporal', 'Temporal Workflow Service'),
    ], string='مُحَوِّل مسارات العمل (Workflow Backend)',
       config_parameter='utility.workflow_adapter',
       default='local', required=True)

    media_backend = fields.Selection([
        ('attachment', 'Odoo Attachments (Database/Filestore)'),
        ('filesystem', 'Local Shared Filesystem'),
        ('s3', 'S3 Compatible Cloud Storage'),
    ], string='مُحَوِّل الوسائط والصور (Media Backend)',
       config_parameter='utility.media_backend',
       default='attachment', required=True)

    # إعدادات Temporal
    temporal_target_host = fields.Char(
        string='عنوان خادم Temporal Host',
        config_parameter='utility.temporal_target_host',
        default='localhost:7233')
    temporal_namespace = fields.Char(
        string='نطاق Temporal Namespace',
        config_parameter='utility.temporal_namespace',
        default='default')

    # إعدادات Filesystem
    filesystem_storage_path = fields.Char(
        string='مسار تخزين الملفات (Filesystem Path)',
        config_parameter='utility.filesystem_storage_path')

    # إعدادات S3
    s3_endpoint_url = fields.Char(
        string='رابط خادم S3 Endpoint URL',
        config_parameter='utility.s3_endpoint_url')
    s3_bucket_name = fields.Char(
        string='اسم الحاوية S3 Bucket Name',
        config_parameter='utility.s3_bucket_name')
    s3_access_key = fields.Char(
        string='مفتاح الوصول S3 Access Key',
        config_parameter='utility.s3_access_key')
    s3_secret_key = fields.Char(
        string='المفتاح السري S3 Secret Key',
        config_parameter='utility.s3_secret_key')
    s3_region_name = fields.Char(
        string='المنطقة S3 Region',
        config_parameter='utility.s3_region_name',
        default='us-east-1')

    @api.constrains('workflow_backend', 'temporal_target_host', 'media_backend', 'filesystem_storage_path', 's3_endpoint_url', 's3_bucket_name', 's3_access_key', 's3_secret_key')
    def _check_infrastructure_backend_config(self):
        for rec in self:
            if rec.workflow_backend == 'temporal':
                raise ValidationError(_("مُحَوِّل Temporal Workflow حاليًا في مرحلة العقد الأولي (Placeholder Contract) وغير جاهز للإنتاج. يُرجى اختيار Local Odoo (In-Process Outbox)."))

            if rec.media_backend == 's3':
                raise ValidationError(_("مُحَوِّل S3 Cloud Storage حاليًا في مرحلة العقد الأولي (Placeholder Contract) وغير جاهز للإنتاج. يُرجى اختيار Odoo Attachments أو Local Shared Filesystem."))

            if rec.media_backend == 'filesystem' and not rec.filesystem_storage_path:
                raise ValidationError(_("عند اختيار Filesystem يجب تحديد مسار تخزين الملفات."))
