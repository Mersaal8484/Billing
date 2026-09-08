import sys
import psycopg2

sys.stdout.reconfigure(encoding="utf-8")

try:
    c = psycopg2.connect(
        host="localhost",
        port=5432,
        user="odoo16",
        password="odoo16",
        dbname="invoice_utility_erp",
    )
except Exception as e:
    print("فشل الاتصال بقاعدة البيانات:", e)
    sys.exit(1)

cur = c.cursor()


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# 1) حالات القراءات (state) منذ بداية سبتمبر
section("STATES - توزيع حالات القراءات")
cur.execute(
    """
    SELECT state, count(*)
    FROM utility_reading
    WHERE reading_date >= %s
    GROUP BY 1
    ORDER BY 1
    """,
    ("2026-09-01",),
)
for row in cur.fetchall():
    print(row)

# 2) آخر 25 قراءة مع كل الحقول المتعلقة بالفوترة
section("RECENT READINGS - آخر القراءات وحالتها التفصيلية")
cur.execute(
    """
    SELECT id, reading_id, state, billing_error, included_sale_order_id,
           date_range_id, is_billable, reading_purpose
    FROM utility_reading
    WHERE reading_date >= %s
    ORDER BY id DESC
    LIMIT 25
    """,
    ("2026-09-01",),
)
for row in cur.fetchall():
    print(row)

# 3) أوامر البيع (الفواتير المخصصة) الأخيرة
section("ORDERS - أوامر البيع / الفواتير الأخيرة")
cur.execute(
    """
    SELECT so.id, so.name, so.state, so.customer_id, so.reading_id, so.date_order
    FROM sale_order so
    WHERE so.date_order >= %s AND so.customer_id IS NOT NULL
    ORDER BY so.id DESC
    LIMIT 15
    """,
    ("2026-09-01",),
)
for row in cur.fetchall():
    print(row)

# 4) الفواتير المحاسبية الحقيقية (account.move)
section("MOVES - الفواتير المحاسبية (account.move)")
cur.execute(
    """
    SELECT am.id, am.name, am.state, am.move_type, am.invoice_date
    FROM account_move am
    WHERE am.move_type IN ('out_invoice', 'out_refund')
      AND am.create_date >= %s
    ORDER BY am.id DESC
    LIMIT 15
    """,
    ("2026-09-01",),
)
for row in cur.fetchall():
    print(row)

# 5) توزيع الحالات لكل القراءات التي فيها خطأ فوترة مسجل
section("ERROR STATES - توزيع حالات القراءات التي فيها خطأ فوترة")
cur.execute(
    """
    SELECT state, count(*)
    FROM utility_reading
    WHERE billing_error IS NOT NULL AND billing_error <> ''
    GROUP BY 1
    """
)
for row in cur.fetchall():
    print(row)

# 6) تفاصيل آخر 15 خطأ فوترة (النص الفعلي - هذا الأهم للتشخيص)
section("BILLING ERRORS - تفاصيل آخر أخطاء الفوترة")
cur.execute(
    """
    SELECT id, reading_id, state, left(billing_error, 240)
    FROM utility_reading
    WHERE billing_error IS NOT NULL AND billing_error <> ''
    ORDER BY id DESC
    LIMIT 15
    """
)
rows = cur.fetchall()
if not rows:
    print("(لا توجد أي قراءة مسجل عليها billing_error)")
for row in rows:
    print(row)

# 7) المهام المجدولة (Cron) المتعلقة بالفوترة وحالتها وموعد التشغيل القادم
section("CRONS - مهام الفوترة المجدولة")
cur.execute(
    """
    SELECT id, name, active, interval_number, interval_type, nextcall
    FROM ir_cron
    WHERE name ILIKE %s OR code ILIKE %s OR code ILIKE %s
    ORDER BY id
    """,
    ("%فوتر%", "%_cron_generate_bills%", "%cron_queue_approved%"),
)
rows = cur.fetchall()
if not rows:
    print("(لم يتم العثور على أي مهمة مجدولة مطابقة)")
for row in rows:
    print(row)

cur.close()
c.close()
