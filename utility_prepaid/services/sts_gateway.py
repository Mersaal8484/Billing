import logging
from abc import ABC, abstractmethod

_logger = logging.getLogger(__name__)


class STSGateway(ABC):
    """Abstract gateway interface for STS (Standard Transfer Specification) providers.

    Defines the contract that all STS provider implementations must follow.
    Use get_provider() factory method to obtain a concrete provider instance
    based on the provider type configuration.
    """

    def __init__(self, env):
        """Initialize with an Odoo environment.

        Args:
            env: Odoo environment.
        """
        self.env = env

    @abstractmethod
    def generate_credit_token(self, request):
        """Generate a credit (recharge) token from the STS provider.

        Args:
            request: utility.vending.request record.

        Returns:
            dict with token_value, token_identifier, provider_reference,
            success, raw_response, response_code, error_message.
        """
        raise NotImplementedError("Subclasses must implement generate_credit_token()")

    @abstractmethod
    def generate_management_token(self, request, token_type):
        """Generate a management token (e.g., tamper reset, key change).

        Args:
            request: utility.vending.request record.
            token_type: str type of management token ('tamper_reset',
                'key_change', 'clear_credit', etc.).

        Returns:
            dict with token_value, success, and response details.
        """
        raise NotImplementedError("Subclasses must implement generate_management_token()")

    @abstractmethod
    def query_transaction(self, provider_reference):
        """Query the status of a transaction from the STS provider.

        Args:
            provider_reference: provider's reference/transaction ID.

        Returns:
            dict with state, success, raw_response, and transaction details.
        """
        raise NotImplementedError("Subclasses must implement query_transaction()")

    @abstractmethod
    def reverse_transaction(self, transaction):
        """Reverse/cancel a previously generated token.

        Args:
            transaction: utility.sts.transaction record to reverse.

        Returns:
            dict with success, raw_response, error_message.
        """
        raise NotImplementedError("Subclasses must implement reverse_transaction()")

    @abstractmethod
    def health_check(self):
        """Check the health/connectivity of the STS provider.

        Returns:
            dict with healthy (bool), message, response_time_ms.
        """
        raise NotImplementedError("Subclasses must implement health_check()")

    def get_provider(self, provider_record):
        """Factory method to get the correct provider instance.

        Args:
            provider_record: utility.sts.provider record.

        Returns:
            BaseSTSProvider subclass instance.
        """
        provider_type = provider_record.provider_type
        provider_class = self._get_provider_class(provider_type)
        if provider_class:
            return provider_class(provider_record)
        raise NotImplementedError(
            f"No provider implementation for type: {provider_type}"
        )

    def _get_provider_class(self, provider_type):
        """Map provider type string to implementation class.

        Args:
            provider_type: str from utility.sts.provider.provider_type.

        Returns:
            class or None.
        """
        from .providers.base_provider import BaseSTSProvider
        from .providers.generic_rest_provider import GenericRestProvider
        from .providers.generic_soap_provider import GenericSoapProvider
        from .providers.hexing_provider import HexingProvider
        from .providers.inhemeter_provider import InhemeterProvider
        from .providers.landis_gyr_provider import LandisGyrProvider

        mapping = {
            'generic_rest': GenericRestProvider,
            'generic_soap': GenericSoapProvider,
            'hexing': HexingProvider,
            'inhemeter': InhemeterProvider,
            'landis_gyr': LandisGyrProvider,
        }
        return mapping.get(provider_type)
