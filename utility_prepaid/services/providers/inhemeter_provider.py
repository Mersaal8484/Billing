import logging
import json

from .base_provider import BaseSTSProvider

_logger = logging.getLogger(__name__)


class InhemeterProvider(BaseSTSProvider):
    """Inhemeter STS provider implementation.

    Implements the Inhemeter-specific protocol for STS token generation
    and management operations.
    """

    def generate_credit_token(self, request):
        """Generate a credit token via Inhemeter API.

        Args:
            request: utility.vending.request record.

        Returns:
            dict with token generation result.
        """
        meter_number = request.meter_id.meter_number or ''
        payload = {
            'meterNumber': meter_number,
            'amount': request.energy_amount,
            'kwh': request.kwh_purchased,
            'reference': request.reference,
            'command': 'CREDIT',
        }
        return self._make_request('/inhemeter/api/token/generate', payload)

    def generate_management_token(self, request, token_type):
        """Generate a management token via Inhemeter API.

        Args:
            request: utility.vending.request record.
            token_type: type of management token.

        Returns:
            dict with token generation result.
        """
        meter_number = request.meter_id.meter_number or ''
        inhemeter_command = self._map_command(token_type)

        payload = {
            'meterNumber': meter_number,
            'reference': request.reference,
            'command': inhemeter_command,
        }
        return self._make_request('/inhemeter/api/token/management', payload)

    def query_transaction(self, provider_reference):
        """Query transaction status from Inhemeter.

        Args:
            provider_reference: Inhemeter transaction reference.

        Returns:
            dict with transaction status.
        """
        payload = {'transactionId': provider_reference}
        return self._make_request(
            '/inhemeter/api/transaction/status',
            payload,
            method='GET',
        )

    def reverse_transaction(self, transaction):
        """Reverse a token via Inhemeter API.

        Args:
            transaction: utility.sts.transaction record.

        Returns:
            dict with reversal result.
        """
        payload = {
            'tokenValue': transaction.token_value,
            'meterNumber': transaction.meter_id.meter_number or '',
            'transactionId': transaction.provider_reference,
            'command': 'REVERSE',
        }
        return self._make_request('/inhemeter/api/token/reverse', payload)

    def health_check(self):
        """Check Inhemeter service connectivity.

        Returns:
            dict with health status.
        """
        return self._make_request(
            '/inhemeter/api/health', {}, method='GET',
        )

    def _map_command(self, token_type):
        """Map generic token type to Inhemeter command string.

        Args:
            token_type: str generic token type.

        Returns:
            str: Inhemeter command string.
        """
        mapping = {
            'tamper_reset': 'TAMPER_RESET',
            'key_change': 'KEY_CHANGE',
            'clear_credit': 'CLEAR_CREDIT',
            'max_credit': 'SET_MAX_CREDIT',
            'disconnect': 'DISCONNECT',
            'reconnect': 'RECONNECT',
        }
        return mapping.get(token_type, 'MANAGEMENT')

    def _build_auth_headers(self):
        """Build Inhemeter-specific authentication headers.

        Returns:
            dict of HTTP headers.
        """
        headers = super()._build_auth_headers()
        if self.api_key:
            headers['X-Inhemeter-AppKey'] = self.api_key
        return headers

    def _parse_response(self, response):
        """Parse Inhemeter-specific JSON response.

        Args:
            response: requests.Response object.

        Returns:
            dict with parsed response data.
        """
        try:
            data = response.json()
        except ValueError:
            return {
                'raw_response': response.text,
                'success': False,
                'error_code': 'PARSE_ERROR',
                'error_message': 'Invalid JSON response',
            }

        inh_data = data.get('data', data)
        result = {
            'raw_response': response.text,
            'success': data.get('success', data.get('code') == 200),
            'token_value': inh_data.get('tokenValue') or inh_data.get('token'),
            'token_identifier': inh_data.get('tokenIdentifier') or inh_data.get('tid'),
            'provider_reference': inh_data.get('transactionId') or inh_data.get('refNo'),
            'response_code': data.get('code') or inh_data.get('responseCode', '00'),
            'response_message': data.get('message') or inh_data.get('message', ''),
        }
        return result
