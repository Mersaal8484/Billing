{
    'name': 'Utility Prepaid',
    'version': '16.0.3.2.0',
    'category': 'Utility ERP',
    'summary': 'مرحلة لاحقة: محرك بيع الكهرباء مسبقة الدفع (متكامل مع POS)',
    'description': """
مرحلة لاحقة — محرك بيع الكهرباء مسبقة الدفع المتكامل
========================================
هذه الوحدة خارج نطاق الإصدار الحالي المخصص لشركة واحدة، ولا تُثبت أو تُشغل قبل اعتماد مرحلة البيع المسبق.

يشمل:
- إدارة طلبات البيع (Vending Requests)
- توليد وإدارة رموز STS
- تكامل نقاط البيع POS
- ورديات الكاشير
- استقطاع الديون
- العكس والتسويات
- أحداث AMI
- التقارير ولوحات المعلومات
    """,
    'author': 'Utility ERP Platform',
    'website': 'https://www.utility-erp.com',
    'license': 'LGPL-3',
    'depends': [
        'utility_core',
        'utility_billing',
        'point_of_sale',
        'account',
        'product',
        'sms',
    ],
    'data': [
        'security/utility_prepaid_security.xml',
        'security/ir.model.access.csv',
        'data/utility_prepaid_sequence.xml',
        'data/utility_prepaid_products.xml',
        'data/utility_prepaid_channels.xml',
        'data/utility_prepaid_reversal_reasons.xml',
        'data/utility_prepaid_cron.xml',
        'data/utility_prepaid_sample_data.xml',
        'views/vending_request_views.xml',
        'views/utility_token_views.xml',
        'views/sts_provider_views.xml',
        'views/sts_transaction_views.xml',
        'views/utility_transaction_views.xml',
        'views/cashier_shift_views.xml',
        'views/debt_recovery_policy_views.xml',
        'views/vending_reversal_views.xml',
        'views/prepaid_adjustment_views.xml',
        'views/ami_event_views.xml',
        'views/prepaid_dashboard_views.xml',
        'views/res_config_settings_views.xml',
        'views/pos_order_views.xml',
        'views/utility_customer_views.xml',
        'views/menus.xml',
        'report/utility_reports.xml',
    ],
    'demo': ['data/utility_demo.xml'],
    'assets': {
        'web.assets_backend': [
            'utility_prepaid/static/src/scss/**/*.scss',
        ],
        'point_of_sale._assets_pos': [
            'utility_prepaid/static/src/js/**/*.js',
            'utility_prepaid/static/src/xml/**/*.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 2,
}
