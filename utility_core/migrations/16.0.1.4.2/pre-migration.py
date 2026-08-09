"""Prepare dedicated accounting partners before the unique constraint is created."""

import logging

from odoo import SUPERUSER_ID


_logger = logging.getLogger(__name__)


def _table_exists(cr, table_name):
    cr.execute('SELECT to_regclass(%s)', [table_name])
    return bool(cr.fetchone()[0])


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
        """,
        [table_name, column_name],
    )
    return bool(cr.fetchone())


def _create_partner_copy(cr, source_partner_id, customer_number):
    cr.execute(
        """
        INSERT INTO res_partner (
            name, active, is_company, customer_rank,
            open_balance, pec_credit, is_credit_raised, credit_raise_date,
            national_id, register_number,
            create_uid, create_date, write_uid, write_date
        )
        SELECT COALESCE(name, '') || ' - حساب كهرباء ' || %s,
               active, is_company, GREATEST(customer_rank, 1),
               open_balance, pec_credit, is_credit_raised, credit_raise_date,
               national_id, register_number,
               %s, NOW(), %s, NOW()
          FROM res_partner
         WHERE id = %s
        RETURNING id
        """,
        [customer_number, SUPERUSER_ID, SUPERUSER_ID, source_partner_id],
    )
    row = cr.fetchone()
    if not row:
        raise RuntimeError(
            'Unable to create dedicated partner for utility customer %s'
            % customer_number
        )
    return row[0]


def migrate(cr, version):
    if not _table_exists(cr, 'utility_customer'):
        return

    if not _column_exists(cr, 'utility_customer', 'owner_partner_id'):
        cr.execute(
            'ALTER TABLE utility_customer '
            'ADD COLUMN owner_partner_id INTEGER REFERENCES res_partner(id)'
        )

    cr.execute(
        """
        UPDATE utility_customer
           SET owner_partner_id = partner_id
         WHERE owner_partner_id IS NULL AND partner_id IS NOT NULL
        """
    )

    cr.execute(
        """
        SELECT partner_id, ARRAY_AGG(id ORDER BY id)
          FROM utility_customer
         WHERE partner_id IS NOT NULL
         GROUP BY partner_id
        HAVING COUNT(*) > 1
        """
    )
    duplicate_groups = cr.fetchall()

    for source_partner_id, customer_ids in duplicate_groups:
        _logger.warning(
            'Migrating shared accounting partner %s for utility customers %s',
            source_partner_id,
            customer_ids,
        )
        for customer_id in customer_ids:
            cr.execute(
                'SELECT customer_number FROM utility_customer WHERE id = %s',
                [customer_id],
            )
            customer_number = cr.fetchone()[0]
            dedicated_partner_id = _create_partner_copy(
                cr, source_partner_id, customer_number)
            cr.execute(
                """
                UPDATE utility_customer
                   SET owner_partner_id = %s, partner_id = %s
                 WHERE id = %s
                """,
                [source_partner_id, dedicated_partner_id, customer_id],
            )

            if _table_exists(cr, 'sale_order'):
                cr.execute(
                    'UPDATE sale_order SET partner_id = %s WHERE customer_id = %s',
                    [dedicated_partner_id, customer_id],
                )
            if _table_exists(cr, 'account_move') and _table_exists(cr, 'sale_order'):
                cr.execute(
                    """
                    UPDATE account_move move
                       SET partner_id = %s
                     WHERE move.utility_sale_order_id IN (
                               SELECT id FROM sale_order WHERE customer_id = %s
                           )
                    """,
                    [dedicated_partner_id, customer_id],
                )
                if _table_exists(cr, 'account_move_line'):
                    cr.execute(
                        """
                        UPDATE account_move_line line
                           SET partner_id = %s
                          FROM account_move move
                         WHERE line.move_id = move.id
                           AND move.utility_sale_order_id IN (
                               SELECT id FROM sale_order WHERE customer_id = %s
                           )
                        """,
                        [dedicated_partner_id, customer_id],
                    )
            if _table_exists(cr, 'account_payment') and _table_exists(cr, 'sale_order'):
                cr.execute(
                    """
                    UPDATE account_payment payment
                       SET partner_id = %s
                     WHERE payment.utility_sale_order_id IN (
                               SELECT id FROM sale_order WHERE customer_id = %s
                           )
                    """,
                    [dedicated_partner_id, customer_id],
                )

        if _table_exists(cr, 'account_move_line') and _table_exists(cr, 'account_move'):
            cr.execute(
                """
                SELECT COUNT(*)
                  FROM account_move_line line
                  JOIN account_move move ON move.id = line.move_id
                 WHERE line.partner_id = %s
                   AND move.state = 'posted'
                   AND line.account_id IN (
                       SELECT id FROM account_account
                        WHERE account_type = 'asset_receivable'
                   )
                   AND move.utility_sale_order_id IS NULL
                """,
                [source_partner_id],
            )
            ambiguous_count = cr.fetchone()[0]
            if ambiguous_count:
                _logger.error(
                    'Ambiguous receivable lines left on owner partner %s: %s. '
                    'They were intentionally not reassigned.',
                    source_partner_id,
                    ambiguous_count,
                )

    # Re-sync every linked accounting document after duplicate handling. This
    # also repairs legacy records whose partner was edited independently of
    # the utility account, using the explicit customer link as the authority.
    if _table_exists(cr, 'sale_order'):
        cr.execute(
            """
            UPDATE sale_order order_rec
               SET partner_id = customer.partner_id
              FROM utility_customer customer
             WHERE order_rec.customer_id = customer.id
               AND order_rec.partner_id IS DISTINCT FROM customer.partner_id
            """
        )
    if (_table_exists(cr, 'account_move') and _table_exists(cr, 'sale_order')
            and _column_exists(cr, 'account_move', 'utility_sale_order_id')):
        cr.execute(
            """
            UPDATE account_move move
               SET partner_id = customer.partner_id
              FROM sale_order order_rec
              JOIN utility_customer customer
                ON customer.id = order_rec.customer_id
             WHERE move.utility_sale_order_id = order_rec.id
               AND move.partner_id IS DISTINCT FROM customer.partner_id
            """
        )
        if _table_exists(cr, 'account_move_line'):
            cr.execute(
                """
                UPDATE account_move_line line
                   SET partner_id = customer.partner_id
                  FROM account_move move
                  JOIN sale_order order_rec
                    ON order_rec.id = move.utility_sale_order_id
                  JOIN utility_customer customer
                    ON customer.id = order_rec.customer_id
                 WHERE line.move_id = move.id
                   AND line.partner_id IS DISTINCT FROM customer.partner_id
                """
            )
    if (_table_exists(cr, 'account_payment') and _table_exists(cr, 'sale_order')
            and _column_exists(cr, 'account_payment', 'utility_sale_order_id')):
        cr.execute(
            """
            UPDATE account_payment payment
               SET partner_id = customer.partner_id
              FROM sale_order order_rec
              JOIN utility_customer customer
                ON customer.id = order_rec.customer_id
             WHERE payment.utility_sale_order_id = order_rec.id
               AND payment.partner_id IS DISTINCT FROM customer.partner_id
            """
        )
