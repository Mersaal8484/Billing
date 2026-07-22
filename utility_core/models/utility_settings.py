from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='العملة',
        readonly=True,
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
