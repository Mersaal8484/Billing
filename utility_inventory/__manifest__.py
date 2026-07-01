{
    'name': 'Utility Inventory Integration',
    'version': '16.0.1.0.0',
    'category': 'Industries/Utilities',
    'summary': 'Integration of Utility Meters with Stock and Inventory',
    'description': """
Utility Inventory Integration
===========================
Bridges the Utility Core with Odoo's Stock module to treat meters as 
serialized products. Allows transferring meters to regions and assigning 
them to customers.
    """,
    'author': 'Utility ERP Platform',
    'website': 'https://www.utility-erp.com',
    'license': 'LGPL-3',
    'depends': ['utility_core', 'stock'],
    'data': [
        'data/utility_inventory_data.xml',
        'views/utility_meter_views.xml',
        'views/utility_region_views.xml',
        'wizards/utility_customer_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'sequence': 15,
}
