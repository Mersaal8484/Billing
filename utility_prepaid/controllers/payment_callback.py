import hashlib
import hmac
import json
import logging

from odoo import http, fields, _
from odoo.http import request, Response
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PaymentCallbackController(http.Controller):
    """Payment gateway callback handler for vending payment confirmation."""

    def _verify_signature(self, provider, data, signature):
        if not provider or not provider.api_secret:
            _logger.warning('No API secret configured for payment verification')
            return False

        raw = json.dumps(data, sort_keys=True, separators=(',', ':'))
        expected = hmac.new(
            provider.api_secret.encode('utf-8'),
            raw.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    @http.route('/payment/callback/<string:provider>', type='http', auth='none', methods=['POST'], csrf=False)
    def payment_callback(self, provider, **kw):
        try:
            data = request.get_json_data() or {}
        except Exception:
            data = {}

        signature = request.httprequest.headers.get('X-Signature') or data.pop('signature', None)
        reference = data.get('reference') or data.get('order_reference')
        payment_status = data.get('status') or data.get('payment_status')
        transaction_id = data.get('transaction_id')

        if not reference:
            return Response(
                json.dumps({'status': 'error', 'message': 'Missing reference'}),
                status=400,
                mimetype='application/json',
            )

        try:
            vending_request = request.env['utility.vending.request'].sudo().search([
                ('reference', '=', reference),
            ], limit=1)

            if not vending_request:
                return Response(
                    json.dumps({'status': 'error', 'message': 'Vending request not found'}),
                    status=404,
                    mimetype='application/json',
                )

            if signature:
                sts_provider = vending_request.company_id.default_sts_provider_id
                if sts_provider and not self._verify_signature(sts_provider, data, signature):
                    _logger.warning('Invalid payment signature for reference %s', reference)
                    return Response(
                        json.dumps({'status': 'error', 'message': 'Invalid signature'}),
                        status=401,
                        mimetype='application/json',
                    )

            if payment_status in ('paid', 'completed', 'success', 'authorized'):
                if vending_request.state in ('draft', 'quoted', 'confirmed'):
                    vending_request.write({
                        'state': 'paid',
                        'paid_date': fields.Datetime.now(),
                    })
                    _logger.info(
                        'Payment confirmed for vending request %s via %s',
                        reference, provider,
                    )

                    if vending_request.company_id.auto_submit_sts:
                        vending_request._generate_tokens()

                payment_values = {
                    'name': data.get('transaction_id', reference),
                    'body': f'Payment callback for {reference}: {payment_status}',
                    'status': 'success',
                    'related_model': 'utility.vending.request',
                    'related_id': vending_request.id,
                    'notes': f'Payment via {provider}, status: {payment_status}',
                }
                try:
                    request.env['utility.prepaid.integration.log'].sudo().create(payment_values)
                except Exception:
                    _logger.exception('Failed to log payment callback')

            elif payment_status in ('failed', 'declined', 'cancelled'):
                vending_request.write({
                    'last_error': f'Payment {payment_status}: {data.get("message", "")}',
                })
                _logger.warning(
                    'Payment failed for vending request %s: %s',
                    reference, payment_status,
                )

            return Response(
                json.dumps({'status': 'ok', 'reference': reference}),
                status=200,
                mimetype='application/json',
            )

        except Exception as e:
            _logger.exception('Payment callback error for provider %s', provider)
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}),
                status=500,
                mimetype='application/json',
            )
