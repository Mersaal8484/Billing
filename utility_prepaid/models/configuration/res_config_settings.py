from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Prepaid settings are inherited from utility_core's config_parameter fields
    # via the company's ir.config_parameter storage

    prepaid_vending_product_id = fields.Many2one('product.product',
        related='company_id.prepaid_vending_product_id', readonly=False,
        string='منتج الشحن المسبق', domain=[('type', '=', 'service')],
        default_model='product.product')

    minimum_vending_amount = fields.Monetary(related='company_id.minimum_vending_amount',
        readonly=False, string='أقل مبلغ شحن')
    maximum_vending_amount = fields.Monetary(related='company_id.maximum_vending_amount',
        readonly=False, string='أقصى مبلغ شحن')
    allow_multiple_meter_vending = fields.Boolean(related='company_id.allow_multiple_meter_vending',
        readonly=False, string='السماح بشحن عدادات متعددة')
    require_selected_customer = fields.Boolean(related='company_id.require_selected_customer',
        readonly=False, string='إلزام اختيار العميل')
    require_open_cashier_shift = fields.Boolean(related='company_id.require_open_cashier_shift',
        readonly=False, string='إلزام وجود وردية مفتوحة')

    default_sts_provider_id = fields.Many2one('utility.sts.provider',
        related='company_id.default_sts_provider_id', readonly=False,
        string='مزود STS الافتراضي', default_model='utility.sts.provider')
    sts_request_timeout = fields.Integer(related='company_id.sts_request_timeout',
        readonly=False, string='مهلة طلب STS (ثانية)')
    sts_max_retry_count = fields.Integer(related='company_id.sts_max_retry_count',
        readonly=False, string='أقصى إعادة محاولة STS')
    enable_automatic_retry = fields.Boolean(related='company_id.enable_automatic_retry',
        readonly=False, string='إعادة محاولة تلقائية')
    enable_provider_status_query = fields.Boolean(related='company_id.enable_provider_status_query',
        readonly=False, string='استعلام حالة المزود')

    mask_token_in_tree_views = fields.Boolean(related='company_id.mask_token_in_tree_views',
        readonly=False, string='إخفاء التوكن في القائمة')
    allow_token_reprint = fields.Boolean(related='company_id.allow_token_reprint',
        readonly=False, string='السماح بإعادة طباعة التوكن')
    token_reprint_limit = fields.Integer(related='company_id.token_reprint_limit',
        readonly=False, string='حد إعادة الطباعة')
    allow_token_resend = fields.Boolean(related='company_id.allow_token_resend',
        readonly=False, string='السماح بإعادة إرسال التوكن')
    token_resend_limit = fields.Integer(related='company_id.token_resend_limit',
        readonly=False, string='حد إعادة الإرسال')
    require_reprint_reason = fields.Boolean(related='company_id.require_reprint_reason',
        readonly=False, string='إلزام سبب إعادة الطباعة')

    prepaid_revenue_policy = fields.Selection(related='company_id.prepaid_revenue_policy',
        readonly=False, string='سياسة الاعتراف بالإيراد')
    prepaid_liability_account_id = fields.Many2one('account.account',
        related='company_id.prepaid_liability_account_id', readonly=False,
        string='حساب الخصم المسبق', default_model='account.account')
    electricity_revenue_account_id = fields.Many2one('account.account',
        related='company_id.electricity_revenue_account_id', readonly=False,
        string='حساب إيراد الكهرباء', default_model='account.account')
    service_charge_revenue_account_id = fields.Many2one('account.account',
        related='company_id.service_charge_revenue_account_id', readonly=False,
        string='حساب إيرادات رسوم الخدمة', default_model='account.account')
    prepaid_tax_account_id = fields.Many2one('account.account',
        related='company_id.prepaid_tax_account_id', readonly=False,
        string='حساب ضريبة الدفع المسبق', default_model='account.account')
    debt_recovery_account_id = fields.Many2one('account.account',
        related='company_id.debt_recovery_account_id', readonly=False,
        string='حساب استقطاع الديون', default_model='account.account')
    prepaid_refund_account_id = fields.Many2one('account.account',
        related='company_id.prepaid_refund_account_id', readonly=False,
        string='حساب استرداد الدفع المسبق', default_model='account.account')
    prepaid_adjustment_account_id = fields.Many2one('account.account',
        related='company_id.prepaid_adjustment_account_id', readonly=False,
        string='حساب تسوية الدفع المسبق', default_model='account.account')
    agent_commission_account_id = fields.Many2one('account.account',
        related='company_id.agent_commission_account_id', readonly=False,
        string='حساب عمولة الوكيل', default_model='account.account')
    prepaid_receivable_account_id = fields.Many2one('account.account',
        related='company_id.prepaid_receivable_account_id', readonly=False,
        string='حساب الذمم المدينة - مسبق', default_model='account.account')
    prepaid_journal_id = fields.Many2one('account.journal',
        related='company_id.prepaid_journal_id', readonly=False,
        string='يومية الدفع المسبق', default_model='account.journal')

    enable_debt_recovery = fields.Boolean(related='company_id.enable_debt_recovery',
        readonly=False, string='تفعيل استقطاع الديون')
    default_debt_policy_id = fields.Many2one('utility.prepaid.debt.policy',
        related='company_id.default_debt_policy_id', readonly=False,
        string='سياسة الديون الافتراضية', default_model='utility.prepaid.debt.policy')
    minimum_energy_percentage = fields.Float(related='company_id.minimum_energy_percentage',
        readonly=False, string='أقل نسبة طاقة بعد الاستقطاع (%)')

    enable_token_sms = fields.Boolean(related='company_id.enable_token_sms',
        readonly=False, string='إرسال التوكن عبر SMS')
    enable_low_credit_alert = fields.Boolean(related='company_id.enable_low_credit_alert',
        readonly=False, string='تنبيه الرصيد المنخفض')
    low_credit_threshold = fields.Float(related='company_id.low_credit_threshold',
        readonly=False, string='حد الرصيد المنخفض (kWh)')
