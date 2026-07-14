{
    'name': 'Utility Migration',
    'version': '16.0.1.0.0',
    'category': 'Industries/Utilities',
    'summary': 'Data Migration for Utility ERP',
    'description': """
Data Migration Module
=====================
Allows importing legacy customers, meters, readings, and opening balances.
    """,
    'author': 'Utility ERP Platform',
    'depends': ['utility_core', 'utility_billing', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/utility_migration_customer_views.xml',
        'wizards/utility_migration_import_wizard_views.xml',
        'views/utility_migration_mapping_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
