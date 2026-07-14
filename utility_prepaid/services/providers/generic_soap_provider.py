import logging
import time
import xml.etree.ElementTree as ET

from .base_provider import BaseSTSProvider

_logger = logging.getLogger(__name__)


class GenericSoapProvider(BaseSTSProvider):
    """Generic SOAP/XML STS provider implementation.

    Uses SOAP XML envelopes for requests and parses XML responses.
    Suitable for legacy STS systems that use SOAP web services.
    """

    SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
    STS_NS = 'http://sts.example.com/service'

    def generate_credit_token(self, request):
        """Generate a credit token using SOAP XML.

        Args:
            request: utility.vending.request record.

        Returns:
            dict with token generation result.
        """
        meter_number = request.meter_id.meter_number or ''
        xml_body = self._build_soap_envelope('GenerateCreditToken', {
            'MeterNumber': meter_number,
            'Amount': request.energy_amount,
            'Kwh': request.kwh_purchased,
            'OrderReference': request.reference,
        })
        return self._make_soap_request('GenerateCreditToken', xml_body)

    def generate_management_token(self, request, token_type):
        """Generate a management token using SOAP XML.

        Args:
            request: utility.vending.request record.
            token_type: type of management token.

        Returns:
            dict with token generation result.
        """
        meter_number = request.meter_id.meter_number or ''
        xml_body = self._build_soap_envelope('GenerateManagementToken', {
            'MeterNumber': meter_number,
            'TokenType': token_type,
            'OrderReference': request.reference,
        })
        return self._make_soap_request('GenerateManagementToken', xml_body)

    def query_transaction(self, provider_reference):
        """Query transaction status via SOAP.

        Args:
            provider_reference: provider's transaction reference.

        Returns:
            dict with transaction status.
        """
        xml_body = self._build_soap_envelope('QueryTransaction', {
            'ProviderReference': provider_reference,
        })
        return self._make_soap_request('QueryTransaction', xml_body)

    def reverse_transaction(self, transaction):
        """Reverse a token via SOAP.

        Args:
            transaction: utility.sts.transaction record.

        Returns:
            dict with reversal result.
        """
        xml_body = self._build_soap_envelope('ReverseTransaction', {
            'TokenValue': transaction.token_value,
            'MeterNumber': transaction.meter_id.meter_number or '',
            'ProviderReference': transaction.provider_reference,
        })
        return self._make_soap_request('ReverseTransaction', xml_body)

    def health_check(self):
        """Check SOAP service health.

        Returns:
            dict with health status.
        """
        xml_body = self._build_soap_envelope('HealthCheck', {})
        return self._make_soap_request('HealthCheck', xml_body)

    def _build_soap_envelope(self, action, params):
        """Build a SOAP XML envelope for the given action.

        Args:
            action: SOAP action name.
            params: dict of parameters to include in the body.

        Returns:
            str: SOAP XML string.
        """
        params_xml = ''
        for key, value in params.items():
            if value is not None:
                params_xml += f'<{key}>{self._xml_escape(str(value))}</{key}>'

        envelope = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<soapenv:Envelope xmlns:soapenv="{self.SOAP_NS}" '
            f'xmlns:sts="{self.STS_NS}">'
            f'<soapenv:Header/>'
            f'<soapenv:Body>'
            f'<sts:{action}>{params_xml}</sts:{action}>'
            f'</soapenv:Body>'
            f'</soapenv:Envelope>'
        )
        return envelope

    def _xml_escape(self, text):
        """Escape special XML characters.

        Args:
            text: str to escape.

        Returns:
            str: XML-safe string.
        """
        return (
            text.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;')
        )

    def _make_soap_request(self, action, xml_body):
        """Execute a SOAP request with proper headers.

        Args:
            action: SOAP action name.
            xml_body: str XML payload.

        Returns:
            dict with parsed SOAP response.
        """
        import requests

        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': f'"{self.STS_NS}/{action}"',
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        url = self.base_url
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    url, data=xml_body.encode('utf-8'),
                    headers=headers, timeout=self.timeout,
                )
                response.raise_for_status()
                return self._parse_soap_response(response)

            except requests.exceptions.Timeout:
                last_error = f"Timeout on attempt {attempt}"
                _logger.warning(
                    "SOAP request timeout (attempt %d/%d) for %s",
                    attempt, self.max_retries, self.name,
                )
            except requests.exceptions.ConnectionError:
                last_error = f"Connection error on attempt {attempt}"
                _logger.warning(
                    "SOAP connection error (attempt %d/%d) for %s",
                    attempt, self.max_retries, self.name,
                )
            except requests.exceptions.HTTPError as e:
                last_error = f"HTTP error: {e}"
                _logger.error("SOAP HTTP error for %s: %s", self.name, e)
                return self._handle_error(e)
            except Exception as e:
                last_error = str(e)
                _logger.exception(
                    "Unexpected SOAP error (attempt %d/%d) for %s",
                    attempt, self.max_retries, self.name,
                )

            if attempt < self.max_retries:
                time.sleep(self.retry_interval)

        from odoo.exceptions import UserError
        raise UserError(
            f"SOAP provider '{self.name}' failed after {self.max_retries} attempts: {last_error}"
        )

    def _parse_soap_response(self, response):
        """Parse SOAP XML response into a result dict.

        Args:
            response: requests.Response object.

        Returns:
            dict with parsed response data.
        """
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            return {
                'success': False,
                'error_code': 'PARSE_ERROR',
                'error_message': 'Invalid XML response',
                'raw_response': response.text,
            }

        ns = {'soap': self.SOAP_NS, 'sts': self.STS_NS}
        body = root.find('.//soap:Body', ns)
        if body is None:
            body = root.find('.//Body', {})

        fault = body.find('.//soap:Fault', ns) if body is not None else None
        if fault is None:
            fault = body.find('.//Fault', {}) if body is not None else None

        if fault is not None:
            fault_string = fault.find('.//faultstring')
            return {
                'success': False,
                'error_code': 'SOAP_FAULT',
                'error_message': fault_string.text if fault_string is not None else 'SOAP Fault',
                'raw_response': response.text,
            }

        result = {
            'raw_response': response.text,
            'success': True,
        }

        for tag in ('TokenValue', 'token_value', 'Token'):
            elem = root.find(f'.//{tag}')
            if elem is not None and elem.text:
                result['token_value'] = elem.text
                break

        for tag in ('TokenIdentifier', 'token_identifier', 'TID'):
            elem = root.find(f'.//{tag}')
            if elem is not None and elem.text:
                result['token_identifier'] = elem.text
                break

        for tag in ('ProviderReference', 'provider_reference', 'TransactionId'):
            elem = root.find(f'.//{tag}')
            if elem is not None and elem.text:
                result['provider_reference'] = elem.text
                break

        for tag in ('ResponseCode', 'response_code', 'StatusCode'):
            elem = root.find(f'.//{tag}')
            if elem is not None and elem.text:
                result['response_code'] = elem.text
                break

        for tag in ('ResponseMessage', 'response_message', 'Message'):
            elem = root.find(f'.//{tag}')
            if elem is not None and elem.text:
                result['response_message'] = elem.text
                break

        return result
