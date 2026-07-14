import logging
from datetime import datetime

from odoo import fields
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class PrepaidSecurityService:
    """Security and access control service for prepaid vending operations.

    Handles permission validation, token visibility masking, audit logging,
    and approval level enforcement for adjustments and reversals.
    """

    APPROVAL_LEVELS = {
        100: 'operator',
        500: 'supervisor',
        1000: 'manager',
        5000: 'director',
    }

    def __init__(self, env):
        """Initialize with an Odoo environment.

        Args:
            env: Odoo environment.
        """
        self.env = env

    def validate_vending_request(self, request, user):
        """Validate that a user has permission to perform a vending operation.

        Checks company access, user group membership, and shift status.

        Args:
            request: utility.vending.request record.
            user: res.users record.

        Raises:
            UserError: if validation fails.
        """
        request.ensure_one()

        if user.company_id != request.company_id:
            raise UserError(
                f"User {user.name} does not belong to company {request.company_id.name}."
            )

        is_manager = user.has_group('utility_prepaid.group_utility_prepaid_manager')
        is_user = user.has_group('utility_prepaid.group_utility_prepaid_user')
        is_admin = user.has_group('utility_prepaid.group_utility_admin')

        if not (is_manager or is_user or is_admin):
            raise UserError(
                f"User {user.name} does not have prepaid vending permissions."
            )

        if request.shift_id and request.shift_id.state != 'open':
            raise UserError(
                f"Shift {request.shift_id.name} is not open. "
                f"Cannot process vending request."
            )

        if request.channel_id and request.channel_id.require_approval:
            if not is_manager and not is_admin:
                raise UserError(
                    f"Channel {request.channel_id.name} requires manager approval."
                )

        _logger.debug(
            "Vending request %s validated for user %s",
            request.reference, user.name,
        )

    def can_view_full_token(self, token, user):
        """Check if a user has permission to see the full token number.

        Regular users see masked tokens; managers and admins see full tokens.

        Args:
            token: utility.token record.
            user: res.users record.

        Returns:
            bool: True if user can see full token.
        """
        token.ensure_one()

        is_manager = user.has_group('utility_prepaid.group_utility_prepaid_manager')
        is_admin = user.has_group('utility_prepaid.group_utility_admin')
        is_operator = user.has_group('utility_prepaid.group_utility_prepaid_user')

        if is_manager or is_admin:
            return True

        if is_operator:
            if token.customer_id == user.partner_id:
                return True
            if token.vending_request_id and token.vending_request_id.operator_id == user:
                return True

        return False

    def audit_action(self, record, action, user=None, details=None):
        """Create an audit log entry for a prepaid action.

        Args:
            record: any Odoo record being acted upon.
            action: str action name (e.g., 'token_generated', 'reversal_approved').
            user: res.users record (defaults to current user).
            details: optional str additional details.
        """
        user = user or self.env.user

        log_vals = {
            'integration_type': 'other',
            'direction': 'outbound',
            'endpoint': action,
            'status': 'success',
            'related_model': record._name,
            'related_id': record.id,
            'user_id': user.id,
            'notes': details or f"Action '{action}' performed on {record._name} #{record.id}",
        }

        if hasattr(record, 'company_id'):
            log_vals['company_id'] = record.company_id.id
        if hasattr(record, 'provider_id'):
            provider = record.provider_id
            if provider:
                log_vals['provider_id'] = provider.id
        if hasattr(record, 'vending_request_id'):
            req = record.vending_request_id
            if req:
                log_vals['vending_request_id'] = req.id

        try:
            self.env['utility.prepaid.integration.log'].create(log_vals)
        except Exception:
            _logger.exception("Failed to create audit log for action %s", action)

    def validate_adjustment_approval(self, adjustment, user):
        """Validate that a user has the required approval level for an adjustment.

        Args:
            adjustment: utility.prepaid.adjustment record.
            user: res.users record.

        Returns:
            bool: True if user has sufficient approval level.

        Raises:
            UserError: if approval level is insufficient.
        """
        adjustment.ensure_one()
        amount = abs(adjustment.amount or 0)

        required_level = self._get_required_approval_level(amount)
        user_level = self._get_user_approval_level(user)

        if user_level < required_level:
            raise UserError(
                f"Insufficient approval level for adjustment of {amount:.2f}. "
                f"Required: {required_level}, your level: {user_level}."
            )

        if adjustment.adjustment_type in ('meter_replacement', 'free_units'):
            is_manager = user.has_group('utility_prepaid.group_utility_prepaid_manager')
            is_admin = user.has_group('utility_prepaid.group_utility_admin')
            if not (is_manager or is_admin):
                raise UserError(
                    f"Adjustment type '{adjustment.adjustment_type}' requires manager approval."
                )

        self.audit_action(
            adjustment, 'adjustment_approved', user,
            details=f"Amount: {amount}, Type: {adjustment.adjustment_type}",
        )
        return True

    def validate_reversal_approval(self, reversal, user):
        """Validate that a user has the required approval level for a reversal.

        Args:
            reversal: utility.vending.reversal record.
            user: res.users record.

        Returns:
            bool: True if user has sufficient approval level.

        Raises:
            UserError: if approval level is insufficient.
        """
        reversal.ensure_one()
        amount = abs(reversal.amount or 0)

        if reversal.reversal_type == 'full':
            required_level = self._get_required_approval_level(amount)
        else:
            required_level = self._get_required_approval_level(amount * 0.5)

        user_level = self._get_user_approval_level(user)

        if user_level < required_level:
            raise UserError(
                f"Insufficient approval level for reversal of {amount:.2f}. "
                f"Required: {required_level}, your level: {user_level}."
            )

        self.audit_action(
            reversal, 'reversal_approved', user,
            details=f"Amount: {amount}, Type: {reversal.reversal_type}",
        )
        return True

    def _get_required_approval_level(self, amount):
        """Determine the minimum approval level required for a given amount.

        Args:
            amount: float adjustment/reversal amount.

        Returns:
            int: required approval level threshold.
        """
        if amount <= 100:
            return 100
        elif amount <= 500:
            return 500
        elif amount <= 1000:
            return 1000
        else:
            return 5000

    def _get_user_approval_level(self, user):
        """Determine a user's approval level based on their groups.

        Args:
            user: res.users record.

        Returns:
            int: user's maximum approval level.
        """
        is_admin = user.has_group('utility_prepaid.group_utility_admin')
        is_manager = user.has_group('utility_prepaid.group_utility_prepaid_manager')
        is_supervisor = user.has_group('utility_prepaid.group_utility_prepaid_supervisor')
        is_user = user.has_group('utility_prepaid.group_utility_prepaid_user')

        if is_admin:
            return 5000
        elif is_manager:
            return 1000
        elif is_supervisor:
            return 500
        elif is_user:
            return 100
        return 0
