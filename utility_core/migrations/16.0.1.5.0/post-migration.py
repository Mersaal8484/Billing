"""
Migration script for 16.0.1.5.0:
- Populate utility_staff_role_rel from legacy user_role_id
- Sync user groups for all active staff records
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Create table and index if not exists
    cr.execute("""
        CREATE TABLE IF NOT EXISTS utility_staff_role_rel (
            staff_id INTEGER NOT NULL REFERENCES utility_staff(id) ON DELETE CASCADE,
            role_id INTEGER NOT NULL REFERENCES utility_user_role(id) ON DELETE CASCADE,
            PRIMARY KEY (staff_id, role_id)
        );
        CREATE INDEX IF NOT EXISTS utility_staff_role_rel_staff_idx ON utility_staff_role_rel(staff_id);
        CREATE INDEX IF NOT EXISTS utility_staff_role_rel_role_idx ON utility_staff_role_rel(role_id);
    """)

    # 2. Backfill relation from legacy user_role_id
    cr.execute("""
        INSERT INTO utility_staff_role_rel (staff_id, role_id)
        SELECT id, user_role_id
        FROM utility_staff
        WHERE user_role_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM utility_staff_role_rel
              WHERE staff_id = utility_staff.id AND role_id = utility_staff.user_role_id
          );
    """)

    # 3. Synchronize user groups
    Staff = env['utility.staff'].with_context(active_test=False)
    all_staff = Staff.search([('user_id', '!=', False)])
    if all_staff:
        all_staff._sync_user_groups()
