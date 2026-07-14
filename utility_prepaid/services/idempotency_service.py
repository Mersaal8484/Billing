import logging
import hashlib
from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IdempotencyService:
    """Handles idempotency for vending operations to prevent duplicate transactions.

    Uses idempotency keys on vending requests and time-window based
    duplicate detection to ensure the same vending operation is not
    processed multiple times.
    """

    def __init__(self, env):
        """Initialize with an Odoo environment.

        Args:
            env: Odoo environment.
        """
        self.env = env

    def check_idempotency_key(self, company_id, idempotency_key):
        """Check if an idempotency key has already been used.

        Args:
            company_id: res.company ID.
            idempotency_key: str unique key from the client.

        Returns:
            utility.vending.request record if found, else None.
        """
        if not idempotency_key:
            return None

        request = self.env['utility.vending.request'].search([
            ('company_id', '=', company_id),
            ('idempotency_key', '=', idempotency_key),
        ], limit=1)

        if request:
            _logger.debug(
                "Idempotency key %s matched existing request %s (state=%s)",
                idempotency_key, request.reference, request.state,
            )
        return request

    def create_with_idempotency(self, model, vals, idempotency_key):
        """Create a record only if the idempotency key is not already used.

        Args:
            model: str model name (e.g., 'utility.vending.request').
            vals: dict of field values for create.
            idempotency_key: str unique key.

        Returns:
            tuple: (record, created) where created is bool.
        """
        if not idempotency_key:
            return self.env[model].create(vals), True

        existing = self.env[model].search([
            ('company_id', '=', vals.get('company_id', self.env.company.id)),
            ('idempotency_key', '=', idempotency_key),
        ], limit=1)

        if existing:
            _logger.info(
                "Idempotency key %s already exists, returning record %s",
                idempotency_key, existing.id,
            )
            return existing, False

        vals['idempotency_key'] = idempotency_key
        record = self.env[model].create(vals)
        return record, True

    def handle_pending_request(self, request):
        """Query the STS provider for the status of a pending request.

        Useful for requests stuck in 'token_pending' state. Updates
        the request state based on the provider's response.

        Args:
            request: utility.vending.request record.

        Returns:
            dict with updated status information.
        """
        request.ensure_one()
        if request.state not in ('token_pending', 'token_failed'):
            raise UserError(
                f"Cannot handle pending request in '{request.state}' state."
            )

        sts_tx = self.env['utility.sts.transaction'].search([
            ('vending_request_id', '=', request.id),
            ('state', 'in', ('pending', 'sent')),
        ], limit=1, order='create_date desc')

        if not sts_tx or not sts_tx.provider_reference:
            return {
                'status': 'no_provider_reference',
                'message': 'No provider reference found to query.',
            }

        try:
            result = sts_tx.provider_id.send_query_transaction(
                sts_tx.provider_reference,
            )
            if result.get('success') and result.get('state') == 'success':
                sts_tx._process_sts_response(result)
                if sts_tx.state == 'success' and sts_tx.token_value:
                    self._create_token_for_request(request, sts_tx)
                    request.write({'state': 'token_generated'})
                    return {
                        'status': 'recovered',
                        'message': 'Transaction recovered as successful.',
                        'token_value': sts_tx.token_value,
                    }
            return {
                'status': result.get('state', 'unknown'),
                'message': result.get('response_message', 'Query completed'),
            }
        except Exception as e:
            _logger.exception(
                "Failed to query pending request %s", request.reference,
            )
            return {
                'status': 'query_failed',
                'message': str(e),
            }

    def prevent_duplicate_token(self, account, meter, amount, window_seconds=60):
        """Check for recent similar vending requests to prevent duplicates.

        Looks for requests with the same account, meter, and similar
        amount within a time window.

        Args:
            account: utility.customer record.
            meter: utility.meter record.
            amount: float vending amount.
            window_seconds: int seconds to look back (default 60).

        Returns:
            utility.vending.request record if duplicate found, else None.
        """
        if not account or not meter:
            return None

        cutoff = fields.Datetime.now() - timedelta(seconds=window_seconds)
        tolerance = amount * 0.01

        recent = self.env['utility.vending.request'].search([
            ('account_id', '=', account.id),
            ('meter_id', '=', meter.id),
            ('gross_amount', '>=', amount - tolerance),
            ('gross_amount', '<=', amount + tolerance),
            ('create_date', '>=', cutoff),
            ('state', 'not in', ('cancelled',)),
        ], limit=1, order='create_date desc')

        if recent:
            _logger.warning(
                "Potential duplicate vending detected: account=%s, meter=%s, "
                "amount=%s, window=%ds, existing=%s",
                account.customer_number, meter.meter_number,
                amount, window_seconds, recent.reference,
            )
        return recent

    def generate_idempotency_key(self, account, meter, amount, channel=None):
        """Generate a deterministic idempotency key from request parameters.

        Useful when the client does not provide one.

        Args:
            account: utility.customer record.
            meter: utility.meter record.
            amount: float vending amount.
            channel: optional utility.vending.channel record.

        Returns:
            str: SHA256-based idempotency key.
        """
        raw = f"{account.id}:{meter.id}:{amount}:{channel.id if channel else ''}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _create_token_for_request(self, request, sts_tx):
        """Create a utility.token record from a recovered STS transaction.

        Args:
            request: utility.vending.request record.
            sts_tx: utility.sts.transaction record with success state.
        """
        if not sts_tx.token_value:
            return

        existing = self.env['utility.token'].search([
            ('vending_request_id', '=', request.id),
            ('token_number', '=', sts_tx.token_value),
        ], limit=1)
        if existing:
            return

        self.env['utility.token'].create({
            'vending_request_id': request.id,
            'account_id': request.account_id.id,
            'meter_id': request.meter_id.id,
            'customer_id': request.partner_id.id,
            'token_number': sts_tx.token_value,
            'token_identifier': sts_tx.token_identifier,
            'amount': request.energy_amount,
            'kwh': request.kwh_purchased,
            'status': 'success',
            'response_date': fields.Datetime.now(),
            'response_code': '00',
            'response_message': 'Token recovered from provider query',
            'sts_server': sts_tx.provider_id.name,
            'provider_reference': sts_tx.provider_reference,
        })
