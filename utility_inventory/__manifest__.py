{
    'name': 'Utility Inventory',
    'version': '16.0.1.0.0',
    'category': 'Industries/Utilities',
    'summary': 'Inventory & Warehouse Management Integration',
    'description': """
Utility Inventory Integration Module
====================================
Integrates Utility Core meters with standard Odoo Stock and Product modules.
Adds lot/serial tracking and product association for physical meters.
    """,
    'author': 'Utility ERP Platform',
    'website': 'https://www.utility-erp.com',
    'license': 'LGPL-3',
    'depends': ['utility_core', 'stock', 'product'],
    'data': [
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
