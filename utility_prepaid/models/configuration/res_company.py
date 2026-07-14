from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    prepaid_vending_product_id = fields.Many2one('product.product', 'منتج الشحن المسبق',
        domain=[('type', '=', 'service')],
        help='المنتج المستخدم لعمليات شحن الكهرباء مسبقة الدفع')

    minimum_vending_amount = fields.Monetary('أقل مبلغ شحن', currency_field='currency_id', default=0.0)
    maximum_vending_amount = fields.Monetary('أقصى مبلغ شحن', currency_field='currency_id', default=0.0)
    allow_multiple_meter_vending = fields.Boolean('السماح بشحن عدادات متعددة', default=False)
    require_selected_customer = fields.Boolean('إلزام اختيار العميل', default=True)
    require_open_cashier_shift = fields.Boolean('إلزام وجود وردية مفتوحة', default=True)

    default_sts_provider_id = fields.Many2one('utility.sts.provider', 'مزود STS الافتراضي')
    sts_request_timeout = fields.Integer('مهلة طلب STS (ثانية)', default=30)
    sts_max_retry_count = fields.Integer('أقصى إعادة محاولة STS', default=3)
    sts_retry_interval = fields.Integer('فاصل إعادة محاولة STS (ثانية)', default=5)
    enable_automatic_retry = fields.Boolean('إعادة محاولة تلقائية', default=True)
    enable_provider_status_query = fields.Boolean('استعلام حالة المزود', default=True)

    mask_token_in_tree_views = fields.Boolean('إخفاء التوكن في القائمة', default=True)
    allow_token_reprint = fields.Boolean('السماح بإعادة طباعة التوكن', default=True)
    token_reprint_limit = fields.Integer('حد إعادة الطباعة', default=3)
    allow_token_resend = fields.Boolean('السماح بإعادة إرسال التوكن', default=True)
    token_resend_limit = fields.Integer('حد إعادة الإرسال', default=5)
    require_reprint_reason = fields.Boolean('إلزام سبب إعادة الطباعة', default=False)

    prepaid_revenue_policy = fields.Selection([
        ('immediate', 'اعتراف فوري'),
        ('deferred', 'إيراد مؤجل'),
    ], 'سياسة الاعتراف بالإيراد', default='immediate')

    prepaid_liability_account_id = fields.Many2one('account.account', 'حساب الخصم المسبق',
        domain=[('deprecated', '=', False)])
    electricity_revenue_account_id = fields.Many2one('account.account', 'حساب إيراد الكهرباء',
        domain=[('deprecated', '=', False)])
    service_charge_revenue_account_id = fields.Many2one('account.account', 'حساب إيرادات رسوم الخدمة',
        domain=[('deprecated', '=', False)])
    prepaid_tax_account_id = fields.Many2one('account.account', 'حساب ضريبة الدفع المسبق',
        domain=[('deprecated', '=', False)])
    debt_recovery_account_id = fields.Many2one('account.account', 'حساب استقطاع الديون',
        domain=[('deprecated', '=', False)])
    prepaid_refund_account_id = fields.Many2one('account.account', 'حساب استرداد الدفع المسبق',
        domain=[('deprecated', '=', False)])
    prepaid_adjustment_account_id = fields.Many2one('account.account', 'حساب تسوية الدفع المسبق',
        domain=[('deprecated', '=', False)])
    agent_commission_account_id = fields.Many2one('account.account', 'حساب عمولة الوكيل',
        domain=[('deprecated', '=', False)])
    prepaid_receivable_account_id = fields.Many2one('account.account', 'حساب الذمم المدينة - مسبق',
        domain=[('deprecated', '=', False)])

    prepaid_journal_id = fields.Many2one('account.journal', 'يومية الدفع المسبق',
        domain=[('type', '=', 'general')])

    enable_debt_recovery = fields.Boolean('تفعيل استقطاع الديون', default=True)
    default_debt_policy_id = fields.Many2one('utility.prepaid.debt.policy', 'سياسة الديون الافتراضية')
    minimum_energy_percentage = fields.Float('أقل نسبة طاقة بعد الاستقطاع (%)', default=10.0)

    enable_token_sms = fields.Boolean('إرسال التوكن عبر SMS', default=True)
    enable_low_credit_alert = fields.Boolean('تنبيه الرصيد المنخفض', default=True)
    low_credit_threshold = fields.Float('حد الرصيد المنخفض (kWh)', default=10.0)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_prepaid_product = fields.Boolean('منتج شحن مسبق', default=False,
        help='هل هذا المنتج مخصص لعمليات الشحن المسبق؟')


class PosConfig(models.Model):
    _inherit = 'pos.config'

    prepaid_vending_product_id = fields.Many2one('product.product', 'منتج الشحن المسبق',
        domain=[('type', '=', 'service')],
        help='المنتج المستخدم لعمليات شحن الكهرباء مسبقة الدفع في نقاط البيع')
