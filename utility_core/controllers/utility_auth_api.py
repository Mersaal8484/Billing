"""
أضف هذا الـ controller في:
F:\invo-system\utility_core\controllers\

أنشئ ملف جديد: utility_auth_api.py
أو أضف الدالة لأي controller موجود
"""

from odoo import http
from odoo.http import request


class UtilityAuthApi(http.Controller):

    @http.route(
        '/api/v1/utility/auth/roles',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def get_user_roles(self, **kwargs):
        """
        يُعيد أدوار المستخدم الحالي بناءً على utility.user.role
        أو مجموعات Odoo المرتبطة بحسابه.

        Response:
            {
                "success": true,
                "user": {"id": 5, "name": "كاشف01", "login": "kasher01"},
                "roles": {
                    "is_meter_reader": true,
                    "is_collector": false,
                    "is_supervisor": false
                },
                "assigned_route_ids": [1, 2],
                "assigned_region_ids": [225]
            }
        """
        user = request.env.user

        # تحقق من الأدوار عبر utility.user.role إذا موجود
        is_reader = False
        is_collector = False
        is_supervisor = False
        route_ids = []
        region_ids = []

        try:
            # البحث في utility.user.role
            role = request.env['utility.user.role'].sudo().search(
                [('user_id', '=', user.id)], limit=1
            )
            if role:
                role_code = role.code if hasattr(role, 'code') else ''
                role_name = role.name.lower() if role.name else ''

                is_reader = 'كاشف' in role_name or 'reader' in role_name or role_code == '1222'
                is_collector = 'متحصل' in role_name or 'collector' in role_name
                is_supervisor = 'مشرف' in role_name or 'supervisor' in role_name

                # جلب المسارات/المناطق المخصصة
                if hasattr(role, 'route_ids'):
                    route_ids = role.route_ids.ids
                if hasattr(role, 'region_ids'):
                    region_ids = role.region_ids.ids
        except Exception:
            pass

        # fallback: التحقق من مجموعات Odoo
        if not (is_reader or is_collector or is_supervisor):
            group_names = user.groups_id.mapped('full_name')
            is_reader = any('meter' in g.lower() or 'reader' in g.lower() or 'كاشف' in g for g in group_names)
            is_collector = any('collect' in g.lower() or 'متحصل' in g for g in group_names)
            is_supervisor = any('supervisor' in g.lower() or 'مشرف' in g for g in group_names)

            # إذا لم يُحدد دور → افتراض كاشف
            if not (is_reader or is_collector or is_supervisor):
                is_reader = True

        return {
            'success': True,
            'user': {
                'id': user.id,
                'name': user.name,
                'login': user.login,
            },
            'roles': {
                'is_meter_reader': is_reader,
                'is_collector': is_collector,
                'is_supervisor': is_supervisor,
            },
            'assigned_route_ids': route_ids,
            'assigned_region_ids': region_ids,
        }
