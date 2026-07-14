import logging
import json

from .base_provider import BaseSTSProvider

_logger = logging.getLogger(__name__)


class LandisGyrProvider(BaseSTSProvider):
    """Landis+Gyr GridBridge/STS provider implementation.

    Implements the Landis+Gyr-specific protocol for STS token generation,
    typically used with GridBridge head-end systems.
    """

    def generate_credit_token(self, request):
        """Generate a credit token via Landis+Gyr API.

        Args:
            request: utility.vending.request record.

        Returns:
            dict with token generation result.
        """
        meter_number = request.meter_id.meter_number or ''
        payload = {
            'meterId': meter_number,
            'amount': request.energy_amount,
            'units': request.kwh_purchased,
            'vendingReference': request.reference,
            'transactionType': 'CREDIT',
        }
        return self._make_request('/gridbridge/api/vending', payload)

    def generate_management_token(self, request, token_type):
        """Generate a management token via Landis+Gyr API.

        Args:
            request: utility.vending.request record.
            token_type: type of management token.

        Returns:
            dict with token generation result.
        """
        meter_number = request.meter_id.meter_number or ''
        lg_command = self._map_command(token_type)

        payload = {
            'meterId': meter_number,
            'vendingReference': request.reference,
            'transactionType': 'MANAGEMENT',
            'managementCommand': lg_command,
        }
        return self._make_request('/gridbridge/api/vending/management', payload)

    def query_transaction(self, provider_reference):
        """Query transaction status from Landis+Gyr GridBridge.

        Args:
            provider_reference: GridBridge transaction reference.

        Returns:
            dict with transaction status.
        """
        return self._make_request(
            f'/gridbridge/api/vending/{provider_reference}',
            {},
            method='GET',
        )

    def reverse_transaction(self, transaction):
        """Reverse a token via Landis+Gyr API.

        Args:
            transaction: utility.sts.transaction record.

        Returns:
            dict with reversal result.
        """
        payload = {
            'meterId': transaction.meter_id.meter_number or '',
            'tokenValue': transaction.token_value,
            'originalReference': transaction.provider_reference,
            'transactionType': 'REVERSE',
        }
        return self._make_request('/gridbridge/api/vending/reverse', payload)

    def health_check(self):
        """Check Landis+Gyr GridBridge connectivity.

        Returns:
            dict with health status.
        """
        return self._make_request(
            '/gridbridge/api/health', {}, method='GET',
        )

    def _map_command(self, token_type):
        """Map generic token type to Landis+Gyr command code.

        Args:
            token_type: str generic token type.

        Returns:
            str: Landis+Gyr command identifier.
        """
        mapping = {
            'tamper_reset': 'TAMPER_RESET',
            'key_change': 'KEY_CHANGE_V2',
            'clear_credit': 'CLEAR_CREDIT',
            'max_credit': 'SET_MAX_CREDIT',
            'disconnect': 'RELAY_OFF',
            'reconnect': 'RELAY_ON',
        }
        return mapping.get(token_type, 'GENERIC_MGMT')

    def _build_auth_headers(self):
        """Build Landis+Gyr-specific authentication headers.

        Returns:
            dict of HTTP headers.
        """
        headers = super()._build_auth_headers()
        if self.api_key:
            headers['X-GridBridge-ApiKey'] = self.api_key
        if self.provider.config_json:
            try:
                config = json.loads(self.provider.config_json)
                if config.get('gridbridge', {}).get('client_id'):
                    headers['X-GridBridge-ClientId'] = config['gridbridge']['client_id']
            except (json.JSONDecodeError, AttributeError):
                pass
        return headers

    def _parse_response(self, response):
        """Parse Landis+Gyr-specific JSON response.

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

        result = {
            'raw_response': response.text,
            'success': data.get('status') == 'success' or data.get('success', False),
            'token_value': data.get('token') or data.get('tokenValue'),
            'token_identifier': data.get('tid') or data.get('tokenIdentifier'),
            'provider_reference': data.get('transactionId') or data.get('reference'),
            'response_code': data.get('responseCode') or data.get('code', '00'),
            'response_message': data.get('message') or data.get('description', ''),
        }

        if data.get('error'):
            result['success'] = False
            result['error_code'] = data.get('errorCode', 'UNKNOWN')
            result['error_message'] = data.get('error', '')

        return result
