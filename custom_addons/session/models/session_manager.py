import odoo
from odoo import models, fields, api, _
import os
import re
import time
from datetime import datetime, timedelta
from odoo.exceptions import UserError, AccessDenied
import logging
_logger = logging.getLogger(__name__)


class SessionManager(models.Model):
    _name = 'session.manager'
    _description = 'Session Management System'
    _order = 'last_access desc'

    name = fields.Char(string='Session ID', required=True, index=True)
    user_id = fields.Many2one('res.users', string='User', index=True)
    db_name = fields.Char(string='Database', index=True)
    login = fields.Char(string='Login')
    create_date = fields.Datetime(string='Creation Date')
    last_access = fields.Datetime(string='Last Access', index=True)
    expiry_date = fields.Datetime(string='Expiry Date', index=True)
    ip_address = fields.Char(string='IP Address')
    user_agent = fields.Text(string='User Agent')
    device_type = fields.Char(string='Device Type', compute='_compute_device_info')
    is_active = fields.Boolean(string='Is Active', default=True, index=True)
    session_data = fields.Text(string='Session Data')
    session_file_path = fields.Char(string='Session File Path')
    geoip_country = fields.Char(string='Country')
    geoip_city = fields.Char(string='City')
    policy_id = fields.Many2one('session.policy', string='Applied Policy')
    audit_log_ids = fields.One2many('session.audit.log', 'session_id', string='Audit Logs')

    def _compute_device_info(self):
        """Parse user agent without external library"""
        browser_patterns = {
            'Chrome': r'Chrome/(\d+)',
            'Firefox': r'Firefox/(\d+)',
            'Safari': r'Safari/(\d+)',
            'Edge': r'Edge/(\d+)',
            'IE': r'MSIE (\d+)|Trident.*rv:(\d+)'
        }

        os_patterns = {
            'Windows': r'Windows NT (\d+\.\d+)',
            'Mac OS X': r'Mac OS X (\d+[\.\d]*)',
            'Linux': r'Linux',
            'Android': r'Android (\d+\.\d+)',
            'iOS': r'iPhone|iPad|iPod'
        }

        for session in self:
            if not session.user_agent:
                session.device_type = False
                continue

            ua = session.user_agent
            device_info = []

            # Detect browser
            browser = None
            for b, pattern in browser_patterns.items():
                match = re.search(pattern, ua)
                if match:
                    browser = b
                    break

            # Detect OS
            os_type = None
            for os_name, pattern in os_patterns.items():
                match = re.search(pattern, ua)
                if match:
                    os_type = os_name
                    break

            # Detect mobile devices
            is_mobile = any(m in ua for m in ['Mobile', 'Android', 'iPhone', 'iPad', 'iPod'])

            if is_mobile:
                device_info.append('Mobile')
            if browser:
                device_info.append(browser)
            if os_type:
                device_info.append(os_type)

            session.device_type = ' / '.join(device_info) if device_info else 'Unknown'


    # Enhanced session update method
    def _update_session_info(self, session_path, session_id):
        """Enhanced session update with policy enforcement"""
        try:
            session_store = self.env['ir.http'].root.session_store
            session_data = session_store.get(session_id)
            if not session_data:
                return

            # Get user and apply policy
            user = self.env['res.users'].browse(session_data.uid)
            policy = self._get_applicable_policy(user)

            expiry_date = self._calculate_expiry_date(session_data, policy)

            vals = {
                'name': session_id,
                'user_id': user.id,
                'db_name': session_data.db,
                'login': session_data.login,
                'last_access': fields.Datetime.now(),
                'expiry_date': expiry_date,
                'ip_address': session_data.get('_geoip', {}).get('remote_addr'),
                'geoip_country': session_data.get('_geoip', {}).get('country_name'),
                'geoip_city': session_data.get('_geoip', {}).get('city'),
                'user_agent': session_data.get('_user_agent'),
                'is_active': True,
                'session_data': str({k: v for k, v in session_data.items() if not k.startswith('_')}),
                'session_file_path': session_path,
                'policy_id': policy.id if policy else False,
            }

            session_record = self.search([('name', '=', session_id)], limit=1)
            if not session_record:
                vals['create_date'] = fields.Datetime.now()
                new_session = self.create(vals)
                self._log_audit(new_session, 'login')
            else:
                session_record.write(vals)

            # Apply concurrent session limits
            if policy and policy.max_sessions:
                self._enforce_session_limit(user, policy.max_sessions)

        except Exception as e:
            _logger.error("Error updating session %s: %s", session_id, str(e))
            raise

    # New helper methods
    def _get_applicable_policy(self, user):
        """Find the applicable session policy for user"""
        return self.env['session.policy'].search([
            ('active', '=', True),
            ('user_ids', 'in', user.id)
        ], limit=1, order='priority desc')

    def _calculate_expiry_date(self, session_data, policy):
        """Calculate expiry date based on policy and system settings"""
        if policy and policy.apply_expiry and policy.session_duration:
            return fields.Datetime.now() + timedelta(hours=policy.session_duration)

        default_duration = self.env['ir.config_parameter'].get_param('session_lifetime', 168)
        return fields.Datetime.now() + timedelta(hours=int(default_duration))

    def _enforce_session_limit(self, user, max_sessions):
        """Enforce maximum concurrent sessions"""
        active_sessions = self.search([
            ('user_id', '=', user.id),
            ('is_active', '=', True)
        ], order='last_access asc')

        if len(active_sessions) > max_sessions:
            for session in active_sessions[max_sessions:]:
                session.force_logout()

    def _log_audit(self, session, action, details=None):
        """Create audit log entry"""
        return self.env['session.audit.log'].create({
            'user_id': session.user_id.id,
            'session_id': session.id,
            'action': action,
            'ip_address': session.ip_address,
            'details': details or f"Session {action} from {session.device_type or 'unknown device'}"
        })

    # Enhanced force logout with audit logging
    def force_logout(self):
        """Enhanced force logout with policy checks"""
        for session in self:
            try:
                session_store = self.env['ir.http'].root.session_store
                if session_store.get(session.name):
                    session_store.delete(session.name)
                if os.path.exists(session.session_file_path):
                    os.unlink(session.session_file_path)

                session.write({
                    'is_active': False,
                    'expiry_date': fields.Datetime.now(),
                    'session_data': 'Terminated by admin'
                })

                self._log_audit(session, 'force_logout', 'Session terminated by administrator')

            except Exception as e:
                _logger.error("Session termination failed: %s", str(e))
                raise UserError(_("Termination error: %s") % str(e))

    # Enhanced session extension with policy checks
    def extend_session(self, hours):
        """Session extension with policy validation"""
        for session in self:
            if not session.is_active:
                raise UserError(_("Cannot extend inactive session"))

            policy = session.policy_id
            if policy and not policy.allow_extension:
                raise UserError(_("Session extension not allowed by policy"))

            try:
                session_store = self.env['ir.http'].root.session_store
                session_data = session_store.get(session.name)
                if session_data:
                    new_expiry = datetime.now() + timedelta(hours=hours)
                    session_data['expiry_date'] = fields.Datetime.to_string(new_expiry)
                    session_store.save(session_data)
                    session.write({
                        'expiry_date': new_expiry,
                        'is_active': True
                    })
                    self._log_audit(session, 'extension', f"Extended by {hours} hours")
            except Exception as e:
                raise UserError(_("Error extending session: %s") % str(e))

    # Enhanced cleanup with batch processing
    def cleanup_expired_sessions(self, batch_size=100):
        """Optimized session cleanup with batch processing"""
        expired_sessions = self.search([
            ('is_active', '=', True),
            ('expiry_date', '<', fields.Datetime.now())
        ], limit=batch_size)

        for session in expired_sessions:
            try:
                session.force_logout()
            except Exception as e:
                _logger.error("Failed to cleanup session %s: %s", session.name, str(e))

    @api.model
    def cron_update_sessions(self):
        """Update session information periodically"""
        session_dir = odoo.tools.config.session_dir
        if not os.path.exists(session_dir):
            _logger.warning("Session directory does not exist: %s", session_dir)
            return

        try:
            for dirname in os.listdir(session_dir):
                dirpath = os.path.join(session_dir, dirname)
                if os.path.isdir(dirpath) and len(dirname) == 2:
                    for filename in os.listdir(dirpath):
                        if len(filename) == 32:  # Session ID length
                            session_path = os.path.join(dirpath, filename)
                            if os.path.isfile(session_path):
                                self._update_session_info(session_path, filename)
        except Exception as e:
            _logger.error("Error updating sessions: %s", str(e))

    def force_logout(self):
        """Force logout selected sessions"""
        for session in self:
            try:
                if os.path.exists(session.session_file_path):
                    os.unlink(session.session_file_path)
                session.write({
                    'is_active': False,
                    'expiry_date': fields.Datetime.now()
                })
            except PermissionError:
                raise UserError(_("Permission denied when trying to delete session file"))
            except Exception as e:
                raise UserError(_("Error terminating session: %s") % str(e))

    def extend_session(self, hours):
        """Extend session duration"""
        for session in self:
            try:
                session_store = self.env['ir.http'].root.session_store
                session_data = session_store.get(session.name)
                if session_data:
                    new_expiry = datetime.now() + timedelta(hours=hours)
                    session_data['expiry_date'] = fields.Datetime.to_string(new_expiry)
                    session_store.save(session_data)
                    session.write({
                        'expiry_date': new_expiry,
                        'is_active': True
                    })
            except Exception as e:
                raise UserError(_("Error extending session: %s") % str(e))

    def cleanup_expired_sessions(self):
        """Cleanup expired sessions"""
        expired_sessions = self.search([
            ('is_active', '=', True),
            ('expiry_date', '<', fields.Datetime.now())
        ])
        expired_sessions.force_logout()


class SessionAuditLog(models.Model):
    _name = 'session.audit.log'
    _description = 'Session Audit Log'
    _order = 'create_date DESC'

    user_id = fields.Many2one('res.users', string='User', index=True)
    session_id = fields.Many2one('session.manager', string='Session')
    action = fields.Selection([
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('force_logout', 'Forced Logout'),
        ('extension', 'Session Extension'),
        ('policy_change', 'Policy Change'),
        ('access_denied', 'Access Denied')
    ], string='Action', index=True)
    ip_address = fields.Char(string='IP Address', index=True)
    details = fields.Text(string='Details')
    create_date = fields.Datetime(string='Timestamp', default=fields.Datetime.now)

    # Method to quickly log actions
    @api.model
    def quick_log(self, user_id, session_id, action, details=None, ip=None):
        return self.create({
            'user_id': user_id,
            'session_id': session_id,
            'action': action,
            'details': details or action,
            'ip_address': ip or self.env.context.get('remote_addr')
        })


class SessionPolicy(models.Model):
    _name = 'session.policy'
    _description = 'Session Security Policies'
    _order = 'priority desc, name'

    name = fields.Char(string='Policy Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    priority = fields.Integer(string='Priority', default=10)
    user_ids = fields.Many2many('res.users', string='Applied Users')
    group_ids = fields.Many2many('res.groups', string='Applied Groups')
    max_sessions = fields.Integer(string='Max Concurrent Sessions')
    allowed_ips = fields.Text(
        string='Allowed IPs',
        help="Comma-separated list of allowed IP addresses/subnets (e.g., 192.168.1.1, 192.168.1.0/24)")
    session_duration = fields.Integer(
        string='Session Duration (hours)',
        help="Maximum session duration before requiring reauthentication")
    apply_expiry = fields.Boolean(
        string='Enforce Session Expiry',
        help="Enforce the session duration limit")
    allow_extension = fields.Boolean(
        string='Allow Session Extension',
        help="Allow users to extend their sessions beyond the initial duration")
    restrict_device = fields.Boolean(
        string='Restrict Device Changes',
        help="Prevent login from different devices simultaneously")
    notify_admins = fields.Boolean(
        string='Notify Administrators',
        help="Send notifications to administrators when policy violations occur")

    # Method to get users affected by this policy
    def get_affected_users(self):
        self.ensure_one()
        users = self.user_ids
        if self.group_ids:
            users += self.group_ids.mapped('users')
        return users

    # Method to apply policy to all affected users
    def apply_to_users(self):
        for policy in self:
            users = policy.get_affected_users()
            for user in users:
                # Update existing sessions
                sessions = self.env['session.manager'].search([
                    ('user_id', '=', user.id),
                    ('is_active', '=', True)
                ])

                for session in sessions:
                    session.write({'policy_id': policy.id})
                    if policy.apply_expiry and policy.session_duration:
                        session.extend_session(policy.session_duration)

                # Update user's max sessions if this policy is more restrictive
                if policy.max_sessions and (not user.max_sessions or policy.max_sessions < user.max_sessions):
                    user.write({'max_sessions': policy.max_sessions})