import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NotificationEngine:
    """Handles notifications for prepaid vending operations.

    Supports SMS, WhatsApp, and integration log notifications.
    Uses Odoo's SMS module or local WhatsApp provider as configured.
    Does NOT use email/mail module.
    """

    def __init__(self, env):
        """Initialize with an Odoo environment.

        Args:
            env: Odoo environment.
        """
        self.env = env

    def send_token_notification(self, token, method='sms'):
        """Send a token notification to the customer.

        Args:
            token: utility.token record.
            method: str 'sms' or 'whatsapp'.

        Returns:
            bool: True if notification sent successfully.
        """
        token.ensure_one()
        if not token.token_number:
            _logger.warning(
                "Cannot send token notification: no token number for token %s",
                token.id,
            )
            return False

        partner = token.customer_id
        if not partner:
            _logger.warning(
                "Cannot send token notification: no customer for token %s",
                token.id,
            )
            return False

        message = self._build_token_message(token)

        if method == 'whatsapp':
            return self._send_whatsapp(partner, message)
        return self._send_sms(partner, message)

    def send_low_credit_alert(self, meter, account, balance):
        """Send a low credit warning to the customer.

        Args:
            meter: utility.meter record.
            account: utility.customer record.
            balance: float remaining credit balance.

        Returns:
            bool: True if notification sent successfully.
        """
        if not account or not account.partner_id:
            return False

        partner = account.partner_id
        threshold = account.company_id.low_credit_threshold or 50

        if balance >= threshold:
            return False

        message = (
            f"Low credit alert: Your meter {meter.meter_number} "
            f"has {balance:.2f} remaining balance. "
            f"Please recharge soon to avoid disconnection."
        )
        return self._send_sms(partner, message)

    def send_vending_confirmation(self, request):
        """Send a vending completion confirmation notification.

        Args:
            request: utility.vending.request record.

        Returns:
            bool: True if notification sent successfully.
        """
        request.ensure_one()
        token = request.token_ids.filtered(
            lambda t: t.status == 'success',
        )
        if not token:
            _logger.warning(
                "No successful token found for vending request %s",
                request.reference,
            )
            return False

        return self.send_token_notification(token[0])

    def send_payment_receipt(self, request):
        """Send a payment confirmation receipt.

        Args:
            request: utility.vending.request record.

        Returns:
            bool: True if notification sent successfully.
        """
        request.ensure_one()
        partner = request.partner_id
        if not partner:
            return False

        company = request.company_id
        message = (
            f"Payment Receipt - {company.name}\n"
            f"Reference: {request.reference}\n"
            f"Meter: {request.meter_id.meter_number}\n"
            f"Amount: {request.gross_amount:.2f}\n"
            f"Energy: {request.kwh_purchased:.3f} kWh\n"
            f"Date: {request.paid_date or request.vending_date}\n"
            f"Status: Paid"
        )
        return self._send_sms(partner, message)

    def _send_sms(self, partner, message):
        """Send an SMS message to a partner.

        Uses Odoo's SMS module or logs to integration provider.

        Args:
            partner: res.partner record.
            message: str message body.

        Returns:
            bool: True if SMS sent or logged successfully.
        """
        if not partner or not partner.phone:
            _logger.warning("No phone number for partner %s", partner.id)
            return False

        try:
            sms_vals = {
                'name': 'Prepaid Vending Notification',
                'body': message,
                'number': partner.phone,
            }
            self.env['sms.sms'].sudo().create(sms_vals)
            _logger.info(
                "SMS sent to %s for partner %s", partner.phone, partner.id,
            )
            return True
        except Exception:
            _logger.exception("Failed to send SMS to %s", partner.phone)
            self._log_notification(partner, 'sms', message, 'failed')
            return False

    def _send_whatsapp(self, partner, message):
        """Send a WhatsApp message via integration provider.

        Args:
            partner: res.partner record.
            message: str message body.

        Returns:
            bool: True if message logged for WhatsApp provider.
        """
        if not partner or not partner.phone:
            _logger.warning("No phone number for WhatsApp to partner %s", partner.id)
            return False

        try:
            self.env['utility.integration.provider'].create({
                'partner_id': partner.id,
                'message_type': 'whatsapp',
                'message_body': message,
                'phone_number': partner.phone,
                'state': 'pending',
            })
            _logger.info(
                "WhatsApp message queued for %s", partner.phone,
            )
            return True
        except Exception:
            _logger.exception(
                "Failed to queue WhatsApp message for %s", partner.phone,
            )
            self._log_notification(partner, 'whatsapp', message, 'failed')
            return False

    def _build_token_message(self, token):
        """Format an SMS message with token details.

        Args:
            token: utility.token record.

        Returns:
            str: formatted message.
        """
        company = token.company_id
        return (
            f"{company.name} - Electricity Token\n"
            f"Token: {token.token_number}\n"
            f"Meter: {token.meter_id.meter_number}\n"
            f"Energy: {token.kwh:.3f} kWh\n"
            f"Amount: {token.amount:.2f}\n"
            f"Ref: {token.vending_request_id.reference if token.vending_request_id else ''}"
        )

    def _log_notification(self, partner, method, message, status):
        """Log a notification attempt to the integration log.

        Args:
            partner: res.partner record.
            method: str 'sms' or 'whatsapp'.
            message: str message body.
            status: str 'success' or 'failed'.
        """
        try:
            self.env['utility.prepaid.integration.log'].create({
                'integration_type': 'sms' if method == 'sms' else 'other',
                'direction': 'outbound',
                'endpoint': method,
                'request_payload': message[:500],
                'status': status,
                'related_model': 'res.partner',
                'related_id': partner.id,
            })
        except Exception:
            _logger.exception("Failed to log notification for partner %s", partner.id)
