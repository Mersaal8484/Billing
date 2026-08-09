"""Populate explicit utility invoice links without guessing ambiguous payments."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE account_payment payment
           SET utility_invoice_id = candidate.move_id
          FROM (
              SELECT payment.id AS payment_id, MIN(move.id) AS move_id,
                     COUNT(move.id) AS move_count
                FROM account_payment payment
                JOIN sale_order order_rec
                  ON order_rec.id = payment.utility_sale_order_id
                JOIN account_move move
                  ON move.utility_sale_order_id = order_rec.id
                 AND move.state = 'posted'
                 AND move.move_type IN ('out_invoice', 'out_refund')
               WHERE payment.utility_sale_order_id IS NOT NULL
                 AND payment.utility_invoice_id IS NULL
               GROUP BY payment.id
          ) candidate
         WHERE payment.id = candidate.payment_id
           AND candidate.move_count = 1
        """
    )
    cr.execute(
        """
        SELECT COUNT(*)
          FROM account_payment payment
         WHERE payment.utility_sale_order_id IS NOT NULL
           AND payment.utility_invoice_id IS NULL
        """
    )
    ambiguous_count = cr.fetchone()[0]
    if ambiguous_count:
        _logger.error(
            'Utility payment migration left %s payments without an explicit '
            'invoice because their bill ownership was ambiguous.',
            ambiguous_count,
        )
