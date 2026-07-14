import logging
import json

from .base_provider import BaseSTSProvider

_logger = logging.getLogger(__name__)


class GenericRestProvider(BaseSTSProvider):
    """Generic REST API STS provider implementation.

    Uses standard JSON-based REST endpoints for all STS operations.
    Suitable for providers that follow common REST API patterns.
    """

    def generate_credit_token(self, request):
        """Generate a credit token using REST API.

        Args:
            request: utility.vending.request record.

        Returns:
            dict with token generation result.
        """
        meter_number = request.meter_id.meter_number or ''
        payload = {
            'meter_number': meter_number,
            'amount': request.energy_amount,
            'kwh': request.kwh_purchased,
            'token_type': 'credit',
            'order_reference': request.reference,
            'vending_date': request.vending_date.isoformat() if request.vending_date else None,
        }

        extra_params = self._get_extra_params()
        if extra_params:
            payload.update(extra_params)

        return self._make_request('/api/v1/tokens/credit', payload)

    def generate_management_token(self, request, token_type):
        """Generate a management token using REST API.

        Args:
            request: utility.vending.request record.
            token_type: type of management token.

        Returns:
            dict with token generation result.
        """
        meter_number = request.meter_id.meter_number or ''
        payload = {
            'meter_number': meter_number,
            'token_type': token_type,
            'order_reference': request.reference,
        }
        return self._make_request('/api/v1/tokens/management', payload)

    def query_transaction(self, provider_reference):
        """Query transaction status via REST API.

        Args:
            provider_reference: provider's transaction reference.

        Returns:
            dict with transaction status.
        """
        return self._make_request(
            f'/api/v1/transactions/{provider_reference}',
            {},
            method='GET',
        )

    def reverse_transaction(self, transaction):
        """Reverse a token via REST API.

        Args:
            transaction: utility.sts.transaction record.

        Returns:
            dict with reversal result.
        """
        payload = {
            'token_value': transaction.token_value,
            'meter_number': transaction.meter_id.meter_number or '',
            'provider_reference': transaction.provider_reference,
            'reason': 'Operator reversal',
        }
        return self._make_request('/api/v1/transactions/reverse', payload)

    def health_check(self):
        """Check REST API health endpoint.

        Returns:
            dict with health status.
        """
        return self._make_request('/api/v1/health', {}, method='GET')

    def _get_extra_params(self):
        """Get additional parameters from provider config JSON.

        Returns:
            dict of extra parameters or empty dict.
        """
        import json as json_mod
        if self.provider.config_json:
            try:
                config = json_mod.loads(self.provider.config_json)
                return config.get('extra_params', {})
            except (json_mod.JSONDecodeError, AttributeError):
                pass
        return {}
