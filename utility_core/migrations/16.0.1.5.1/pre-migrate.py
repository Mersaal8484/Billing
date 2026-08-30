"""
Migration 16.0.1.5.1 — pre-migrate
حذف الـ inherited view القديم الذي يحتوي على xpath يبحث عن supervisor_id
بعد دمج المشرف مع طاقم العمل في utility_route_views.xml
"""


def migrate(cr, version):
    """
    نحذف سجل ir.ui.view الخاص بـ view_utility_route_form_inherited
    حتى يُعيد Odoo إنشاءه نظيفاً من ملف utility_route_assignment_wizard_views.xml.
    """
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE model = 'utility.route'
          AND name = 'utility.route.form.assignment.wizard'
          AND arch_db::text LIKE '%%supervisor_id%%'
    """)
    deleted = cr.rowcount
    if deleted:
        cr.execute("SELECT id FROM ir_ui_view WHERE name = 'utility.route.form.assignment.wizard'")
        remaining = cr.fetchall()
        print(
            f"[migration 16.0.1.5.1] حُذف {deleted} سجل(ات) من ir_ui_view "
            f"(utility.route.form.assignment.wizard) يحتوي على supervisor_id. "
            f"المتبقي: {remaining}"
        )
    else:
        print(
            "[migration 16.0.1.5.1] لم يُعثر على سجل يحتوي supervisor_id — "
            "لا شيء للحذف (ربما تم تنظيفه مسبقاً)."
        )
