{
    'name': 'Utility Prepaid',
    'version': '16.0.1.0.0',
    'category': 'Industries/Utilities',
    'summary': 'Prepaid Electricity Vending Engine',
    'description': """
Enterprise Prepaid Electricity Vending Module
===============================================
Complete prepaid vending engine with STS token management,
payment processing, cashier balancing, and receipt generation.

Models: Sale, Sale Line, Payment, Token, Transaction,
Adjustment, Reversal, Receipt, Cashier Shift.
    """,
    'author': 'Utility ERP Platform',
    'website': 'https://www.utility-erp.com',
    'license': 'LGPL-3',
    'depends': ['utility_core', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/utility_sequence.xml',
        'views/utility_sale_views.xml',
        'views/utility_payment_views.xml',
        'views/utility_token_views.xml',
        'views/utility_transaction_views.xml',
        'views/utility_adjustment_views.xml',
        'views/utility_reversal_views.xml',
        'views/utility_cashier_views.xml',
        'views/utility_prepaid_menu.xml',
        'report/utility_receipt_report.xml',
        'report/utility_reports.xml',
    ],
    'demo': ['data/utility_demo.xml'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 20,
}
