from odoo import http
from odoo.http import request

class WebSessionAutoCloseController(http.Controller):
    @http.route("/web/session/get_timeout", type="json", auth="user")
    def get_session_timeout(self):
        # استخدم sudo() للوصول إلى المعلمة
        timeout_sec = request.env['ir.config_parameter'].sudo().get_param(
            'web_session_auto_close.timeout', default=600
        )
        return int(timeout_sec) * 1000  # تحويل الثواني إلى ميلي ثانية