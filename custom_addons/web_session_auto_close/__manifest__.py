{
    "name": "Web Session Auto Close",
    "summary": """Automatically logs out inactive users based on a configurable
    timeout.""",
    "version": "16.0.1.0.1",
    "license": "AGPL-3",
    "author": "ACSONE SA/NV, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/web",
    "depends": ["web","base_setup"],
    "data": ["views/res_config_settings.xml"],

    "assets": {
        "web.assets_backend": [
            'web_session_auto_close\static\src\js\session_monitor.js',
        ],
    },
}