"""Backfill auditable allocations only where the historical link is unambiguous."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Create one historical allocation for invoices with one explicit payment."""
    cr.execute(
        """
        WITH candidates AS (
            SELECT payment.id AS payment_id,
                   payment.utility_customer_id,
                   payment.utility_sale_order_id,
                   payment.utility_invoice_id AS invoice_id,
                   payment.amount,
                   payment.electronic_doc_no,
                   CASE payment.utility_payment_method
                       WHEN 'electronic' THEN 'gateway'
                       WHEN 'bank' THEN 'bank'
                       ELSE 'cashier'
                   END AS source,
                   invoice.amount_residual AS residual_after,
                   invoice.currency_id,
                   payment_move.company_id,
                   payment_move.date AS payment_date,
                   payment_move.create_uid AS payment_create_uid,
                   ROW_NUMBER() OVER (
                       PARTITION BY payment.utility_invoice_id ORDER BY payment.id
                   ) AS invoice_payment_no,
                   COUNT(*) OVER (
                       PARTITION BY payment.utility_invoice_id
                   ) AS invoice_payment_count
              FROM account_payment payment
              JOIN account_move payment_move
                ON payment_move.id = payment.move_id
              JOIN account_move invoice
                ON invoice.id = payment.utility_invoice_id
               AND invoice.state = 'posted'
               AND invoice.move_type = 'out_invoice'
               AND invoice.utility_sale_order_id = payment.utility_sale_order_id
              JOIN utility_customer customer
                ON customer.id = payment.utility_customer_id
               AND customer.partner_id = payment.partner_id
               AND invoice.partner_id = customer.partner_id
             WHERE payment_move.state = 'posted'
               AND payment.payment_type = 'inbound'
               AND payment.utility_invoice_id IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM utility_payment_allocation allocation
                    WHERE allocation.payment_id = payment.id
               )
               AND EXISTS (
                   SELECT 1
                     FROM account_move_line payment_line
                     JOIN account_partial_reconcile partial
                       ON partial.debit_move_id = payment_line.id
                       OR partial.credit_move_id = payment_line.id
                     JOIN account_move_line invoice_line
                       ON (invoice_line.id = partial.debit_move_id
                           OR invoice_line.id = partial.credit_move_id)
                    WHERE payment_line.move_id = payment.move_id
                      AND invoice_line.move_id = invoice.id
                      AND payment_line.partner_id = invoice.partner_id
                      AND invoice_line.partner_id = invoice.partner_id
                      AND payment_line.account_id = invoice_line.account_id
               )
        )
        INSERT INTO utility_payment_allocation (
            name, company_id, payment_id, utility_customer_id, sale_order_id,
            invoice_id, partner_id, currency_id, requested_amount,
            allocated_amount, residual_before, residual_after, allocation_date,
            source, external_reference, state, created_by, create_uid, create_date,
            write_uid, write_date
        )
        SELECT 'MIG-' || candidate.payment_id,
               candidate.company_id, candidate.payment_id,
               candidate.utility_customer_id, candidate.utility_sale_order_id,
               candidate.invoice_id, payment.partner_id, candidate.currency_id,
               candidate.amount, candidate.amount,
               candidate.residual_after + candidate.amount,
               candidate.residual_after, COALESCE(candidate.payment_date, NOW()),
               candidate.source, candidate.electronic_doc_no,
               'reconciled', candidate.payment_create_uid, 1, NOW(), 1, NOW()
          FROM candidates candidate
          JOIN account_payment payment ON payment.id = candidate.payment_id
         WHERE candidate.invoice_payment_no = 1
           AND candidate.invoice_payment_count = 1
           AND NOT EXISTS (
               SELECT 1 FROM utility_payment_allocation allocation
                WHERE allocation.payment_id = candidate.payment_id
           )
        """
    )
    cr.execute(
        """
        SELECT COUNT(*)
          FROM account_payment payment
         JOIN account_move payment_move ON payment_move.id = payment.move_id
         WHERE payment.utility_sale_order_id IS NOT NULL
           AND payment_move.state = 'posted'
           AND payment.utility_invoice_id IS NULL
        """
    )
    ambiguous = cr.fetchone()[0]
    if ambiguous:
        _logger.warning(
            'Skipped %s posted utility payments without an explicit invoice; '
            'they require manual audit and were not guessed.', ambiguous,
        )
