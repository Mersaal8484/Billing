import sys
import psycopg2

sys.stdout.reconfigure(encoding="utf-8")

c = psycopg2.connect(
    host="localhost",
    port=5432,
    user="odoo16",
    password="odoo16",
    dbname="invoice_utility_erp",
)
cur = c.cursor()


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# 1) افحص فترة الفوترة المشكوك فيها (date_range_id = 182)
section("DATE RANGE 182 - تفاصيل الفترة المسببة للمشكلة")
cur.execute(
    """
    SELECT id, name, date_start, date_end, period_type, state
    FROM utility_date_range
    WHERE id = 182
    """
)
for row in cur.fetchall():
    print(row)

# 2) افحص المشتركين المتأثرين ودورة الفوترة المضبوطة على فئتهم
section("AFFECTED CUSTOMERS - دورة الفوترة الفعلية لكل مشترك متأثر")
cur.execute(
    """
    SELECT r.id, r.reading_id, uc.id AS customer_id, uc.customer_number,
           cat.name AS category_name, cat.billing_cycle
    FROM utility_reading r
    LEFT JOIN utility_customer uc ON uc.id = r.customer_id
    LEFT JOIN utility_subscriber_category cat ON cat.id = uc.category_id
    WHERE r.state = 'error'
    ORDER BY r.id DESC
    """
)
for row in cur.fetchall():
    print(row)

# 3) كم فترة فوترة موجودة أصلاً بنفس نوع "نصف شهري" حول نفس التاريخ
section("MATCHING PERIODS - فترات نصف شهرية متاحة بنفس المدى الزمني")
cur.execute(
    """
    SELECT id, name, date_start, date_end, period_type, state
    FROM utility_date_range
    WHERE period_type = 'semi_monthly'
    ORDER BY date_start DESC
    LIMIT 10
    """
)
for row in cur.fetchall():
    print(row)

# 4) فحص أعمدة جدول ir_cron الفعلية (لتصحيح الاستعلام القادم)
section("IR_CRON COLUMNS - أعمدة الجدول الفعلية")
cur.execute(
    """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'ir_cron'
    ORDER BY ordinal_position
    """
)
for row in cur.fetchall():
    print(row)

cur.close()
c.close()
