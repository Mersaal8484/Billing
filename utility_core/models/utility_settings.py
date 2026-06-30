from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

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

    # --- Billing & Invoicing ---
    enable_auto_invoice_confirm = fields.Boolean(
        string='تأكيد الفواتير تلقائياً',
        config_parameter='utility.enable_auto_invoice_confirm',
        default=False)
    auto_generate_bills = fields.Boolean(
        string='توليد الفواتير تلقائياً',
        config_parameter='utility.auto_generate_bills',
        default=True)
    billing_due_days = fields.Integer(
        string='أيام الاستحقاق',
        config_parameter='utility.billing_due_days',
        default=30)
    late_penalty_percentage = fields.Float(
        string='نسبة غرامة التأخير (%)',
        config_parameter='utility.late_penalty_percentage',
        default=1.5)

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

    # --- Prepaid / Emergency ---
    emergency_credit_amount = fields.Float(
        string='قيمة رصيد الطوارئ الافتراضي',
        config_parameter='utility.emergency_credit_amount',
        default=50.0)
    emergency_credit_grace_days = fields.Integer(
        string='فترة سماح رصيد الطوارئ (أيام)',
        config_parameter='utility.emergency_credit_grace_days',
        default=7)
    low_credit_threshold = fields.Float(
        string='حد الرصيد المنخفض',
        config_parameter='utility.low_credit_threshold',
        default=100.0)

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
    send_sms_on_low_credit = fields.Boolean(
        string='إرسال SMS عند انخفاض الرصيد',
        config_parameter='utility.send_sms_on_low_credit',
        default=True)

    # --- Accounting ---
    fine_account_id = fields.Many2one(
        'account.account',
        string='حساب إيرادات الغرامات',
        config_parameter='utility.fine_account_id')
    discount_account_id = fields.Many2one(
        'account.account',
        string='حساب الخصومات / الإعفاءات',
        config_parameter='utility.discount_account_id')
    deposit_account_id = fields.Many2one(
        'account.account',
        string='حساب التأمينات',
        config_parameter='utility.deposit_account_id')
    settlement_account_id = fields.Many2one(
        'account.account',
        string='حساب التسويات المالية',
        config_parameter='utility.settlement_account_id')
    writeoff_journal_id = fields.Many2one(
        'account.journal',
        string='يومية الإعفاءات',
        config_parameter='utility.writeoff_journal_id')
    deposit_journal_id = fields.Many2one(
        'account.journal',
        string='يومية التأمينات والودائع',
        config_parameter='utility.deposit_journal_id')
    settlement_journal_id = fields.Many2one(
        'account.journal',
        string='يومية التسويات',
        config_parameter='utility.settlement_journal_id')
    penalty_product_id = fields.Many2one(
        'product.product',
        string='منتج الغرامات',
        config_parameter='utility.penalty_product_id')
    mu_allim_product_id = fields.Many2one(
        'product.product',
        string='منتج المعلم',
        config_parameter='utility.mu_allim_product_id')
    cleaning_product_id = fields.Many2one(
        'product.product',
        string='منتج النظافة',
        config_parameter='utility.cleaning_product_id')
    local_fee_product_id = fields.Many2one(
        'product.product',
        string='منتج المجالس المحلية',
        config_parameter='utility.local_fee_product_id')
