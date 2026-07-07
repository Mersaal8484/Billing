{
    'name': 'Advanced Session Manager',
    'version': '16.0.1.1.0',
    'summary': 'Comprehensive Session Management and Control',
    'description': """
        Advanced session management system for Odoo 16 including:
        - Real-time session monitoring
        - Force logout capabilities
        - Session lifetime control
        - User activity tracking
        - IP restriction management
        - Multi-device session control
    """,
    'author': 'Bashammakh',
    'website': 'https://www.yourcompany.com',
    'category': 'Tools/Security',
    'depends': ['base', 'web'],
    'data': [
        'security/session_manager_security.xml',
        'security/ir.model.access.csv',
        'views/session_manager_views.xml',
        'views/res_users_views.xml',
        'views/res_config_settings_views.xml',
        'data/session_manager_data.xml',
        'data/session_parameters.xml',
    ],
    'demo': [
        'demo/session_manager_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'session_manager/static/src/js/session_manager.js',
            # 'session_manager/static/src/scss/session_manager.scss',
        ],
        'web.assets_qweb': [
            'session_manager/static/src/xml/session_manager_templates.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}