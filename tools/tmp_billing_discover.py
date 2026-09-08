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


# 1) كل الجداول التي تحتوي كلمة date_range أو period بالاسم
section("TABLES - جداول متعلقة بالفترات (date_range / period)")
cur.execute(
    """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND (table_name ILIKE '%date_range%' OR table_name ILIKE '%period%')
    ORDER BY table_name
    """
)
for row in cur.fetchall():
    print(row)

# 2) كل الجداول المتعلقة بالمشتركين/الفئات
section("TABLES - جداول متعلقة بالمشتركين والفئات (customer / category / subscriber)")
cur.execute(
    """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND (table_name ILIKE '%customer%' OR table_name ILIKE '%subscriber%' OR table_name ILIKE '%category%')
    ORDER BY table_name
    """
)
for row in cur.fetchall():
    print(row)

# 3) أعمدة جدول utility_reading كاملة (لنتأكد من اسم عمود الفترة والمشترك)
section("UTILITY_READING COLUMNS - كل أعمدة جدول القراءات")
cur.execute(
    """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'utility_reading'
    ORDER BY ordinal_position
    """
)
for row in cur.fetchall():
    print(row)

cur.close()
c.close()
