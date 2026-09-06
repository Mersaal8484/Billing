"""Normalize legacy transformer/Zone links before one-to-one SQL constraints load."""


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT zone_region_id, array_agg(id ORDER BY id)
          FROM utility_transformer
         WHERE zone_region_id IS NOT NULL
         GROUP BY zone_region_id
        HAVING COUNT(*) > 1
    """)
    for zone_id, transformer_ids in cr.fetchall():
        cr.execute(
            """
                SELECT name, code, parent_id, company_id, active, recurring_rule_type,
                       transformer_origin_id
                  FROM utility_region
                 WHERE id = %s
            """,
            [zone_id],
        )
        name, code, parent_id, company_id, active, cadence, origin_id = cr.fetchone()
        keeper_id = origin_id if origin_id in transformer_ids else transformer_ids[0]
        for transformer_id in transformer_ids:
            if transformer_id == keeper_id:
                continue
            zone_code = '%s-TRF-%s' % (code, transformer_id)
            cr.execute(
                """
                    INSERT INTO utility_region
                        (name, code, type, parent_id, company_id, active,
                         recurring_rule_type, transformer_origin_id)
                    VALUES (%s, %s, 'zone', %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                [name, zone_code, parent_id, company_id, active, cadence, transformer_id],
            )
            new_zone_id = cr.fetchone()[0]
            cr.execute(
                'UPDATE utility_transformer SET zone_region_id = %s WHERE id = %s',
                [new_zone_id, transformer_id],
            )

    cr.execute("""
        UPDATE utility_region
           SET transformer_origin_id = NULL
         WHERE transformer_origin_id IS NOT NULL
           AND NOT EXISTS (
               SELECT 1
                 FROM utility_transformer transformer
                WHERE transformer.id = utility_region.transformer_origin_id
                  AND transformer.zone_region_id = utility_region.id
           )
    """)
    cr.execute("""
        UPDATE utility_region region
           SET transformer_origin_id = transformer.id
          FROM utility_transformer transformer
         WHERE transformer.zone_region_id = region.id
           AND region.transformer_origin_id IS NULL
    """)
