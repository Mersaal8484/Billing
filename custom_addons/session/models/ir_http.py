# models/ir_http.py

from odoo import models, api, fields, _
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request, root, SessionExpiredException, _logger
import datetime


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'


    @classmethod
    def _should_check_device_restriction(cls, user, request):
        """Check if user has device restriction policies"""
        policies = request.env['session.policy'].search([
            ('active', '=', True),
            ('restrict_device', '=', True),
            ('user_ids', 'in', user.id)
        ])

        if not policies:
            return False

        current_ua = request.httprequest.user_agent.string
        active_sessions = request.env['session.manager'].search([
            ('user_id', '=', user.id),
            ('is_active', '=', True)
        ])

        for session in active_sessions:
            if session.user_agent and not cls._compare_user_agents(current_ua, session.user_agent):
                return True

        return False

    @classmethod
    def _compare_user_agents(cls, ua1, ua2):
        """Basic user agent comparison for device restriction"""
        # Compare major browser and OS
        browsers = ['Chrome', 'Firefox', 'Safari', 'Edge', 'IE']
        os_list = ['Windows', 'Mac OS X', 'Linux', 'Android', 'iOS']

        def get_agent_info(ua):
            return {
                'browser': next((b for b in browsers if b in ua), 'Other'),
                'os': next((os for os in os_list if os in ua), 'Other'),
                'mobile': any(m in ua for m in ['Mobile', 'Android', 'iPhone'])
            }

        info1 = get_agent_info(ua1)
        info2 = get_agent_info(ua2)

        return (info1['browser'] == info2['browser'] and
                info1['os'] == info2['os'] and
                info1['mobile'] == info2['mobile'])

    @classmethod
    def _authenticate(cls, endpoint):
        res = super(IrHttp, cls)._authenticate(endpoint)

        if request.session.uid:
            user = request.env['res.users'].browse(request.session.uid)
            if not user.session_control_enabled:
                return res

            # التحقق من IP
            if user.restrict_ip and request.httprequest.remote_addr not in user.allowed_ips.split(','):
                request.session.logout(keep_db=True)
                raise AccessDenied(_("IP address not allowed"))

            # التحقق من عدد الجلسات
            if user.active_session_count >= user.max_sessions:
                request.session.logout(keep_db=True)
                raise AccessDenied(_("Maximum sessions limit reached"))

            # تسجيل الجلسة الجديدة
            session_manager = request.env['session.manager'].sudo()
            session_manager._update_session_info(
                root.session_store.get_session_filename(request.session.sid),
                request.session.sid
            )

        return res

    @classmethod
    def _post_dispatch(cls, response):
        res = super(IrHttp, cls)._post_dispatch(response)

        if request.session.uid:
            try:
                session_manager = request.env['session.manager'].sudo()
                session = session_manager.search([
                    ('name', '=', request.session.sid),
                    ('is_active', '=', True)
                ], limit=1)

                if session:
                    # تحديث آخر نشاط
                    session.write({
                        'last_access': fields.Datetime.now(),
                        'ip_address': request.httprequest.remote_addr
                    })

                    # التحقق من مدة الجلسة
                    if session.expiry_date < datetime.now():
                        request.session.logout(keep_db=True)
                        raise SessionExpiredException("Session expired")

            except Exception as e:
                _logger.warning("Session update error: %s", str(e))

        return res

    @classmethod
    def _handle_error(cls, exc):
        if isinstance(exc, SessionExpiredException):
            return request.redirect('/web/session/logout?expired=1')
        return super(IrHttp, cls)._handle_error(exc)