"""Populate exact accounting invoices for legacy gateway transactions."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE utility_payment_gateway_transaction tx
           SET utility_invoice_id = candidate.move_id
          FROM (
              SELECT tx.id AS tx_id, MIN(move.id) AS move_id,
                     COUNT(move.id) AS move_count
                FROM utility_payment_gateway_transaction tx
                JOIN sale_order order_rec
                  ON order_rec.id = tx.sale_order_id
                JOIN account_move move
                  ON move.utility_sale_order_id = order_rec.id
                 AND move.state = 'posted'
                 AND move.move_type IN ('out_invoice', 'out_refund')
               WHERE tx.utility_invoice_id IS NULL
               GROUP BY tx.id
          ) candidate
         WHERE tx.id = candidate.tx_id
           AND candidate.move_count = 1
        """
    )
    cr.execute(
        """
        SELECT COUNT(*)
          FROM utility_payment_gateway_transaction
         WHERE utility_invoice_id IS NULL
        """
    )
    ambiguous_count = cr.fetchone()[0]
    if ambiguous_count:
        _logger.error(
            'Gateway migration left %s transactions without an exact invoice. '
            'They require explicit invoice selection and were not guessed.',
            ambiguous_count,
        )
