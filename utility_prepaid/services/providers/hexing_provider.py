import logging
import json
import hashlib
import time

from .base_provider import BaseSTSProvider

_logger = logging.getLogger(__name__)


class HexingProvider(BaseSTSProvider):
    """Hexing HES/STS provider implementation.

    Implements the Hexing-specific STS protocol for token generation
    and management. Supports both REST and proprietary Hexing API formats.
    """

    def generate_credit_token(self, request):
        """Generate a credit token via Hexing HES API.

        Args:
            request: utility.vending.request record.

        Returns:
            dict with token generation result.
        """
        meter_number = request.meter_id.meter_number or ''
        payload = {
            'meterNo': meter_number,
            'amount': request.energy_amount,
            'kwh': request.kwh_purchased,
            'orderNo': request.reference,
            'tokenType': 1,
        }

        hexing_config = self._get_hexing_config()
        if hexing_config.get('use_legacy_format'):
            payload = self._convert_to_legacy_format(payload)

        endpoint = hexing_config.get('token_endpoint', '/api/hes/token/generate')
        return self._make_request(endpoint, payload)

    def generate_management_token(self, request, token_type):
        """Generate a management token via Hexing HES API.

        Args:
            request: utility.vending.request record.
            token_type: type of management token.

        Returns:
            dict with token generation result.
        """
        meter_number = request.meter_id.meter_number or ''
        hexing_token_type = self._map_token_type(token_type)

        payload = {
            'meterNo': meter_number,
            'tokenType': hexing_token_type,
            'orderNo': request.reference,
        }
        endpoint = '/api/hes/token/management'
        return self._make_request(endpoint, payload)

    def query_transaction(self, provider_reference):
        """Query transaction status from Hexing HES.

        Args:
            provider_reference: Hexing transaction reference.

        Returns:
            dict with transaction status.
        """
        payload = {'transactionId': provider_reference}
        return self._make_request('/api/hes/transaction/query', payload, method='GET')

    def reverse_transaction(self, transaction):
        """Reverse a token via Hexing HES.

        Args:
            transaction: utility.sts.transaction record.

        Returns:
            dict with reversal result.
        """
        payload = {
            'tokenValue': transaction.token_value,
            'meterNo': transaction.meter_id.meter_number or '',
            'transactionId': transaction.provider_reference,
            'reason': 'Reversal',
        }
        return self._make_request('/api/hes/token/reverse', payload)

    def health_check(self):
        """Check Hexing HES connectivity.

        Returns:
            dict with health status.
        """
        return self._make_request('/api/hes/health', {}, method='GET')

    def _get_hexing_config(self):
        """Parse Hexing-specific configuration from provider config JSON.

        Returns:
            dict of Hexing configuration parameters.
        """
        default = {
            'use_legacy_format': False,
            'token_endpoint': '/api/hes/token/generate',
            'require_signature': True,
            'api_version': 'v2',
        }
        if self.provider.config_json:
            try:
                config = json.loads(self.provider.config_json)
                return {**default, **config.get('hexing', {})}
            except (json.JSONDecodeError, AttributeError):
                pass
        return default

    def _convert_to_legacy_format(self, payload):
        """Convert modern payload to Hexing legacy API format.

        Args:
            payload: modern dict payload.

        Returns:
            dict in legacy format.
        """
        return {
            'MeterNo': payload.get('meterNo', ''),
            'Amount': payload.get('amount', 0),
            'KWH': payload.get('kwh', 0),
            'OrderNo': payload.get('orderNo', ''),
            'Type': payload.get('tokenType', 1),
        }

    def _map_token_type(self, token_type):
        """Map generic token type to Hexing-specific type code.

        Args:
            token_type: str generic token type.

        Returns:
            int: Hexing token type code.
        """
        mapping = {
            'tamper_reset': 2,
            'key_change': 3,
            'clear_credit': 4,
            'max_credit': 5,
            'disconnect': 6,
            'reconnect': 7,
        }
        return mapping.get(token_type, 2)

    def _build_auth_headers(self):
        """Build Hexing-specific authentication headers.

        Returns:
            dict of HTTP headers.
        """
        headers = super()._build_auth_headers()
        hexing_config = self._get_hexing_config()

        if hexing_config.get('require_signature') and self.api_key and self.api_secret:
            timestamp = str(int(time.time()))
            signature = self._generate_signature(timestamp)
            headers['X-Hexing-Timestamp'] = timestamp
            headers['X-Hexing-Signature'] = signature
            headers['X-Hexing-API-Key'] = self.api_key

        headers['X-Hexing-API-Version'] = hexing_config.get('api_version', 'v2')
        return headers

    def _generate_signature(self, timestamp):
        """Generate HMAC signature for Hexing API authentication.

        Args:
            timestamp: str Unix timestamp.

        Returns:
            str: HMAC-SHA256 signature hex digest.
        """
        import hmac
        message = f"{self.api_key}{timestamp}".encode('utf-8')
        secret = (self.api_secret or '').encode('utf-8')
        return hmac.new(secret, message, hashlib.sha256).hexdigest()
