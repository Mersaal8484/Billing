{
    'name': 'Utility Billing',
    'version': '16.0.1.0.0',
    'category': 'Industries/Utilities',
    'summary': 'Postpaid Billing & Collections Engine',
    'description': """
Enterprise Utility Billing Module
===================================
Postpaid billing engine with meter reading management,
billing cycles, invoice generation, penalty calculation,
debt management, collections, and payment allocation.
    """,
    'author': 'Utility ERP Platform',
    'website': 'https://www.utility-erp.com',
    'license': 'LGPL-3',
    'depends': ['utility_core', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/utility_sequence.xml',
        'data/utility_cron.xml',
        'data/utility_cron_extras.xml',
        'views/utility_reading_views.xml',
        'views/utility_billing_cycle_views.xml',
        'views/utility_bill_views.xml',
        'views/utility_collection_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/financial_settlement_views.xml',
        'views/utility_billing_menu.xml',
    ],
    'demo': ['data/utility_demo.xml'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 40,
}
