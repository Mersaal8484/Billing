"""Resolve legacy duplicate provider references before the unique index."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        WITH duplicates AS (
            SELECT id, provider_id, provider_reference,
                   ROW_NUMBER() OVER (
                       PARTITION BY provider_id, provider_reference ORDER BY id
                   ) AS duplicate_no
              FROM utility_payment_gateway_transaction
             WHERE provider_reference IS NOT NULL
               AND provider_reference <> ''
        )
        UPDATE utility_payment_gateway_transaction tx
           SET provider_reference = tx.provider_reference || '-DUP-' || tx.id
          FROM duplicates d
         WHERE tx.id = d.id AND d.duplicate_no > 1
        """
    )
    _logger.info('Legacy duplicate gateway references were made deterministic.')
