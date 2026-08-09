"""Allow a collection to be settled in more than one settlement document."""

from psycopg2 import sql


def migrate(cr, version):
    """Drop the obsolete one-column uniqueness before ORM creates the new one."""
    cr.execute(
        """
        SELECT c.conname
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
          JOIN pg_attribute a ON a.attrelid = t.oid
                              AND a.attnum = ANY(c.conkey)
         WHERE t.relname = 'utility_collection_settlement_line'
           AND c.contype = 'u'
         GROUP BY c.oid, c.conname
        HAVING array_agg(a.attname ORDER BY a.attnum) = ARRAY['collection_id']::name[]
        """
    )
    for (constraint_name,) in cr.fetchall():
        cr.execute(
            sql.SQL('ALTER TABLE {} DROP CONSTRAINT {}').format(
                sql.Identifier('utility_collection_settlement_line'),
                sql.Identifier(constraint_name),
            )
        )
