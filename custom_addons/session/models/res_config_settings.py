# models/res_config_settings.py

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    session_lifetime = fields.Integer(
        string='Default Session Lifetime (hours)',
        config_parameter='session_lifetime',
        default=168)  # 1 week

    session_extension_enabled = fields.Boolean(
        string='Allow Session Extension',
        config_parameter='session_extension_enabled',
        default=True)

    session_inactivity_timeout = fields.Integer(
        string='Inactivity Timeout (minutes)',
        config_parameter='session_inactivity_timeout',
        default=30)

    session_cleanup_batch_size = fields.Integer(
        string='Cleanup Batch Size',
        config_parameter='session_cleanup_batch_size',
        default=100)

    enable_session_audit = fields.Boolean(
        string='Enable Session Auditing',
        config_parameter='enable_session_audit',
        default=True)

    session_security_level = fields.Selection([
        ('low', 'Low (Basic checks)'),
        ('medium', 'Medium (IP + Device validation)'),
        ('high', 'High (Multi-factor authentication)')
    ], string='Security Level', default='medium')