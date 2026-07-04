{
    'name': 'Utility Inventory',
    'version': '16.0.1.0.0',
    'category': 'Industries/Utilities',
    'summary': 'Inventory & Warehouse Management',
    'description': """
Utility Inventory Module
==========================
Inventory and warehouse management for spare parts, meters, and materials.
Manages storage locations, stock items, movements, and physical inventory counts.

Models: Inventory Location, Inventory Item, Inventory Movement, Inventory Count.
    """,
    'author': 'Utility ERP Platform',
    'website': 'https://www.utility-erp.com',
    'license': 'LGPL-3',
    'depends': ['utility_core', 'stock', 'product'],
    'data': [
        'security/utility_inventory_security.xml',
        'security/ir.model.access.csv',
        'data/utility_sequence.xml',
        'data/utility_inventory_data.xml',
        'views/utility_inventory_location_views.xml',
        'views/utility_inventory_item_views.xml',
        'views/utility_inventory_movement_views.xml',
        'views/utility_inventory_count_views.xml',
        'views/utility_inventory_menu.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 35,
}
