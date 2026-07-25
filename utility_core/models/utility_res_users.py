from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Kept as a compatibility field so databases upgrading from versions that
    # exposed it in res.users views can rebuild the generated groups view.
    # Installment-plan business logic has been removed from utility_billing.
    prevent_installment = fields.Boolean(
        string='منع إنشاء خطط التقسيط (حقل قديم)',
        default=False,
        help='حقل توافق قديم غير مستخدم في منطق النظام الحالي.',
    )
    collection_journal_id = fields.Many2one(
        'account.journal', string='اليومية النقدية للتحصيل',
        domain="[('type', 'in', ('cash', 'bank'))]",
        help='اليومية الخاصة بالمحصل لتسجيل دفعات فواتير الكهرباء')

    collector_block_code = fields.Char(
        string="رمز دفتر التحصيل (Block Code)",
        help="الرمز أو الحرف المخصص لدفاتر تحصيل وقراءات هذا المستخدم"
    )
    legacy_user_code = fields.Char(
        string="كود المستخدم بالنظام القديم (Legacy User Code)",
        help="معرف المستخدم الخاص بالنظام المؤسسي السابق (PEC)"
    )
    assigned_region_ids = fields.Many2many(
        'utility.region', 'res_users_region_rel',
        'user_id', 'region_id',
        string="المناطق المخصصة (Assigned Regions)",
        domain="[('type', '=', 'region')]",
        help="المناطق الجغرافية والتشغيلية المصرح للمستخدم بإدارتها أو العمل فيها"
    )
    assigned_route_ids = fields.Many2many(
        'utility.route', 'res_users_route_rel',
        'user_id', 'route_id',
        string="خطوط السير المخصصة (Assigned Routes)",
        help="خطوط السير الجغرافية المصرح للمستخدم (متحصل أو قارئ) بالعمل فيها"
    )
