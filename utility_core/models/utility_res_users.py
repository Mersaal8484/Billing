from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

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
    prevent_installment = fields.Boolean(
        string="منع الدفع بالتقسيط (Prevent Installment)",
        help="تجريد المستخدم من صلاحية قبول أو جدولة دفعات الفواتير على أقساط"
    )
    assigned_region_ids = fields.Many2many(
        'utility.region', 'res_users_region_rel',
        'user_id', 'region_id',
        string="المناطق المخصصة (Assigned Regions)",
        domain="[('type', '=', 'region')]",
        help="المناطق الجغرافية والتشغيلية المصرح للمستخدم بإدارتها أو العمل فيها"
    )
