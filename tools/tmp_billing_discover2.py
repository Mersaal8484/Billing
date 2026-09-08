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


def show_columns(table):
    section(f"COLUMNS - {table}")
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    for row in cur.fetchall():
        print(row)


show_columns("date_range")
show_columns("date_range_type")
show_columns("utility_subscriber_category")
show_columns("utility_customer")
show_columns("utility_subscriber")

cur.close()
c.close()
