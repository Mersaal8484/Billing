"""Populate exact accounting invoices for legacy gateway transactions."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Repoint every legacy billing document after all customers have a
    # dedicated accounting partner, including singleton accounts.
    cr.execute(
        """
        UPDATE sale_order order_rec
           SET partner_id = customer.partner_id
          FROM utility_customer customer
         WHERE order_rec.customer_id = customer.id
           AND order_rec.partner_id IS DISTINCT FROM customer.partner_id
        """
    )
    cr.execute(
        """
        UPDATE account_move move
           SET partner_id = customer.partner_id,
               utility_customer_id = customer.id
          FROM sale_order order_rec
          JOIN utility_customer customer ON customer.id = order_rec.customer_id
         WHERE move.utility_sale_order_id = order_rec.id
        """
    )
    cr.execute(
        """
        UPDATE account_payment payment
           SET partner_id = customer.partner_id
          FROM utility_customer customer
         WHERE payment.utility_customer_id = customer.id
        """
    )
    cr.execute(
        """
        UPDATE account_move_line line
           SET partner_id = move.partner_id
          FROM account_move move
         WHERE line.move_id = move.id
           AND move.utility_customer_id IS NOT NULL
        """
    )

    # Backfill the audit dimension and partner on opening/payment moves.
    cr.execute(
        """
        UPDATE account_move move
           SET utility_customer_id = customer.id,
               partner_id = customer.partner_id
          FROM utility_customer customer
         WHERE customer.opening_move_id = move.id
        """
    )
    cr.execute(
        """
        UPDATE account_move move
           SET utility_customer_id = payment.utility_customer_id,
               partner_id = customer.partner_id
          FROM account_payment payment
          JOIN utility_customer customer
            ON customer.id = payment.utility_customer_id
         WHERE payment.move_id = move.id
           AND payment.utility_customer_id IS NOT NULL
        """
    )
    cr.execute(
        """
        UPDATE account_move_line line
           SET partner_id = move.partner_id
          FROM account_move move
         WHERE line.move_id = move.id
           AND move.utility_customer_id IS NOT NULL
        """
    )

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
