{
    'name': 'Utility Prepaid',
    'version': '16.0.2.0.0',
    'category': 'Industries/Utilities',
    'summary': 'Prepaid Electricity Vending Engine (POS Based)',
    'description': """
Enterprise Prepaid Electricity Vending Module
===============================================
Prepaid vending engine with STS token management,
POS integration, and cashier balancing.
    """,
    'author': 'Utility ERP Platform',
    'website': 'https://www.utility-erp.com',
    'license': 'LGPL-3',
    'depends': ['utility_core', 'point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/utility_sequence.xml',
        'views/utility_token_views.xml',
        'views/utility_transaction_views.xml',
        'views/utility_adjustment_views.xml',
        'views/utility_reversal_views.xml',
        'views/utility_cashier_views.xml',
        'views/utility_prepaid_menu.xml',
        'report/utility_reports.xml',
    ],
    'demo': ['data/utility_demo.xml'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 20,
}
