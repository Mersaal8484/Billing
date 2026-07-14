import logging
import time

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BaseSTSProvider:
    """Base class for all STS provider implementations.

    Provides common HTTP request handling, authentication, response parsing,
    and error handling. Subclasses override specific methods to implement
    vendor-specific protocols.
    """

    def __init__(self, provider_record):
        """Initialize with an STS provider Odoo record.

        Args:
            provider_record: utility.sts.provider record.
        """
        self.provider = provider_record
        self.name = provider_record.name
        self.code = provider_record.code
        self.base_url = provider_record.base_url
        self.api_key = provider_record.api_key
        self.api_secret = provider_record.api_secret
        self.timeout = provider_record.timeout or 30
        self.max_retries = provider_record.max_retries or 3
        self.retry_interval = provider_record.retry_interval or 5

    def generate_credit_token(self, request):
        """Generate a credit token via HTTP call to the STS provider.

        Args:
            request: utility.vending.request record.

        Returns:
            dict with success, token_value, token_identifier,
            provider_reference, raw_response, response_code.
        """
        meter_number = request.meter_id.meter_number or ''
        payload = {
            'meter_number': meter_number,
            'amount': request.energy_amount,
            'kwh': request.kwh_purchased,
            'token_type': 'credit',
            'order_reference': request.reference,
        }
        return self._make_request('/generate_token', payload)

    def generate_management_token(self, request, token_type):
        """Generate a management token.

        Args:
            request: utility.vending.request record.
            token_type: type of management token.

        Returns:
            dict with success and token details.
        """
        meter_number = request.meter_id.meter_number or ''
        payload = {
            'meter_number': meter_number,
            'token_type': token_type,
            'order_reference': request.reference,
        }
        return self._make_request('/generate_management_token', payload)

    def query_transaction(self, provider_reference):
        """Query transaction status from the provider.

        Args:
            provider_reference: provider's transaction reference.

        Returns:
            dict with success, state, raw_response.
        """
        payload = {'provider_reference': provider_reference}
        return self._make_request('/query_transaction', payload, method='POST')

    def reverse_transaction(self, transaction):
        """Reverse a previously issued token.

        Args:
            transaction: utility.sts.transaction record.

        Returns:
            dict with success, raw_response, error_message.
        """
        payload = {
            'token_value': transaction.token_value,
            'meter_number': transaction.meter_id.meter_number or '',
            'provider_reference': transaction.provider_reference,
        }
        return self._make_request('/reverse_transaction', payload)

    def health_check(self):
        """Check provider connectivity.

        Returns:
            dict with healthy (bool), message, response_time_ms.
        """
        try:
            start = time.time()
            response = self._make_request('/health', {}, method='GET')
            elapsed = (time.time() - start) * 1000
            if response.get('success'):
                return {
                    'healthy': True,
                    'message': 'Provider is healthy',
                    'response_time_ms': elapsed,
                }
            return {
                'healthy': False,
                'message': response.get('error_message', 'Health check failed'),
                'response_time_ms': elapsed,
            }
        except Exception as e:
            _logger.exception("Health check failed for provider %s", self.name)
            return {
                'healthy': False,
                'message': str(e),
                'response_time_ms': 0,
            }

    def _make_request(self, endpoint, payload, method='POST'):
        """Execute an HTTP request to the STS provider with retries.

        Args:
            endpoint: API endpoint path.
            payload: dict of request data.
            method: HTTP method ('GET' or 'POST').

        Returns:
            dict parsed from the response.

        Raises:
            UserError: on repeated failures.
        """
        import requests

        if not self.base_url:
            raise UserError(f"Base URL not configured for provider '{self.name}'.")

        url = f"{self.base_url}{endpoint}"
        headers = self._build_auth_headers()
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if method.upper() == 'GET':
                    response = requests.get(
                        url, headers=headers, timeout=self.timeout, params=payload,
                    )
                else:
                    response = requests.post(
                        url, json=payload, headers=headers, timeout=self.timeout,
                    )

                response.raise_for_status()
                result = self._parse_response(response)
                result['success'] = True
                return result

            except requests.exceptions.Timeout:
                last_error = f"Timeout on attempt {attempt}"
                _logger.warning(
                    "STS request timeout (attempt %d/%d) for %s: %s",
                    attempt, self.max_retries, self.name, endpoint,
                )
            except requests.exceptions.ConnectionError:
                last_error = f"Connection error on attempt {attempt}"
                _logger.warning(
                    "STS connection error (attempt %d/%d) for %s: %s",
                    attempt, self.max_retries, self.name, endpoint,
                )
            except requests.exceptions.HTTPError as e:
                last_error = f"HTTP error: {e}"
                _logger.error(
                    "STS HTTP error for %s: %s - %s",
                    self.name, endpoint, e,
                )
                return self._handle_error(e)
            except Exception as e:
                last_error = str(e)
                _logger.exception(
                    "Unexpected error in STS request (attempt %d/%d) for %s",
                    attempt, self.max_retries, self.name,
                )

            if attempt < self.max_retries:
                time.sleep(self.retry_interval)

        raise UserError(
            f"STS provider '{self.name}' failed after {self.max_retries} attempts: {last_error}"
        )

    def _build_auth_headers(self):
        """Build authentication headers from provider configuration.

        Returns:
            dict of HTTP headers.
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        if self.api_secret:
            headers['X-API-Secret'] = self.api_secret
        return headers

    def _parse_response(self, response):
        """Parse the HTTP response from the STS provider.

        Args:
            response: requests.Response object.

        Returns:
            dict with parsed response data.
        """
        try:
            data = response.json()
        except ValueError:
            data = {'raw_response': response.text}

        return {
            'token_value': data.get('token_value') or data.get('token'),
            'token_identifier': data.get('token_identifier') or data.get('tid'),
            'provider_reference': data.get('provider_reference') or data.get('transaction_id'),
            'response_code': data.get('response_code') or data.get('status_code', '00'),
            'response_message': data.get('response_message') or data.get('message', ''),
            'raw_response': response.text,
        }

    def _handle_error(self, error):
        """Handle and log errors from STS provider communication.

        Args:
            error: Exception that occurred.

        Returns:
            dict with success=False and error details.
        """
        error_msg = str(error)
        error_code = 'UNKNOWN'

        import requests
        if isinstance(error, requests.exceptions.HTTPError):
            if error.response is not None:
                error_code = str(error.response.status_code)
                try:
                    error_body = error.response.json()
                    error_msg = error_body.get('error_message', error_msg)
                except ValueError:
                    error_msg = error.response.text or error_msg

        _logger.error(
            "STS provider %s error [%s]: %s",
            self.name, error_code, error_msg,
        )

        return {
            'success': False,
            'error_code': error_code,
            'error_message': error_msg,
            'raw_response': str(error),
        }
