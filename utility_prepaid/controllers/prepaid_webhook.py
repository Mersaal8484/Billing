import hashlib
import hmac
import json
import logging

from odoo import http, fields, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class PrepaidWebhookController(http.Controller):
    """Webhook handler for external STS and AMI system events."""

    def _verify_webhook_signature(self, payload, signature, secret):
        if not secret:
            _logger.warning('No webhook secret configured')
            return False

        expected = hmac.new(
            secret.encode('utf-8'),
            payload if isinstance(payload, bytes) else payload.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    @http.route('/webhook/sts/<string:provider>', type='http', auth='none', methods=['POST'], csrf=False)
    def webhook_sts(self, provider, **kw):
        payload = request.httprequest.data
        signature = request.httprequest.headers.get('X-Webhook-Signature')

        sts_provider = request.env['utility.sts.provider'].sudo().search([
            ('code', '=', provider),
            ('active', '=', True),
        ], limit=1)

        if not sts_provider:
            _logger.warning('STS webhook received for unknown provider: %s', provider)
            return Response(
                json.dumps({'status': 'error', 'message': 'Provider not found'}),
                status=404,
                mimetype='application/json',
            )

        if signature:
            secret = sts_provider.api_secret or sts_provider.config_json
            if secret and not self._verify_webhook_signature(payload, signature, secret):
                _logger.warning('Invalid STS webhook signature for provider %s', provider)
                return Response(
                    json.dumps({'status': 'error', 'message': 'Invalid signature'}),
                    status=401,
                    mimetype='application/json',
                )

        try:
            data = json.loads(payload) if isinstance(payload, bytes) else json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return Response(
                json.dumps({'status': 'error', 'message': 'Invalid JSON payload'}),
                status=400,
                mimetype='application/json',
            )

        event_type = data.get('event_type') or data.get('type')
        provider_reference = data.get('provider_reference')
        token_value = data.get('token_value')
        state = data.get('state') or data.get('status')

        try:
            if event_type == 'token_generated' or state == 'success':
                sts_tx = request.env['utility.sts.transaction'].sudo().search([
                    ('provider_reference', '=', provider_reference),
                    ('state', 'in', ('pending', 'sent')),
                ], limit=1)

                if sts_tx and token_value:
                    sts_tx._process_sts_response({
                        'success': True,
                        'token_value': token_value,
                        'token_identifier': data.get('token_identifier'),
                        'provider_reference': provider_reference,
                        'raw_response': payload.decode() if isinstance(payload, bytes) else payload,
                        'response_code': data.get('response_code', '00'),
                    })

                    vending_req = sts_tx.vending_request_id
                    if vending_req and vending_req.state == 'token_pending':
                        vending_req.state = 'token_generated'

                elif not sts_tx and token_value:
                    request.env['utility.prepaid.integration.log'].sudo().create({
                        'integration_type': 'other',
                        'direction': 'inbound',
                        'endpoint': f'sts_webhook_{provider}',
                        'status': 'success',
                        'request_payload': payload.decode() if isinstance(payload, bytes) else str(payload),
                        'response_payload': 'Token generated but no matching STS transaction found',
                        'provider_id': sts_provider.id,
                    })

            elif event_type == 'token_failed' or state == 'failed':
                sts_tx = request.env['utility.sts.transaction'].sudo().search([
                    ('provider_reference', '=', provider_reference),
                    ('state', 'in', ('pending', 'sent')),
                ], limit=1)

                if sts_tx:
                    sts_tx.write({
                        'state': 'failed',
                        'error_code': data.get('error_code', 'WEBHOOK_FAILED'),
                        'error_message': data.get('error_message', 'STS webhook reported failure'),
                        'response_date': fields.Datetime.now(),
                        'raw_response': payload.decode() if isinstance(payload, bytes) else payload,
                    })

                    vending_req = sts_tx.vending_request_id
                    if vending_req and vending_req.state == 'token_pending':
                        vending_req.write({
                            'state': 'token_failed',
                            'last_error': data.get('error_message', 'STS webhook reported failure'),
                        })

            request.env['utility.prepaid.integration.log'].sudo().create({
                'integration_type': 'other',
                'direction': 'inbound',
                'endpoint': f'sts_webhook_{provider}',
                'status': 'success',
                'request_payload': payload.decode() if isinstance(payload, bytes) else str(payload)[:500],
                'provider_id': sts_provider.id,
                'notes': f'STS webhook processed: {event_type or state}',
            })

            return Response(
                json.dumps({'status': 'ok'}),
                status=200,
                mimetype='application/json',
            )

        except Exception as e:
            _logger.exception('STS webhook processing error for provider %s', provider)
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}),
                status=500,
                mimetype='application/json',
            )

    @http.route('/webhook/ami/<string:event_type>', type='http', auth='none', methods=['POST'], csrf=False)
    def webhook_ami(self, event_type, **kw):
        payload = request.httprequest.data
        signature = request.httprequest.headers.get('X-Webhook-Signature')

        company = request.env.company
        webhook_secret = getattr(company, 'ami_webhook_secret', None)

        if signature and webhook_secret:
            if not self._verify_webhook_signature(payload, signature, webhook_secret):
                _logger.warning('Invalid AMI webhook signature for event %s', event_type)
                return Response(
                    json.dumps({'status': 'error', 'message': 'Invalid signature'}),
                    status=401,
                    mimetype='application/json',
                )

        try:
            data = json.loads(payload) if isinstance(payload, bytes) else json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return Response(
                json.dumps({'status': 'error', 'message': 'Invalid JSON payload'}),
                status=400,
                mimetype='application/json',
            )

        meter_number = data.get('meter_number') or data.get('meter_id')
        if not meter_number:
            return Response(
                json.dumps({'status': 'error', 'message': 'Missing meter_number'}),
                status=400,
                mimetype='application/json',
            )

        try:
            meter = request.env['utility.meter'].sudo().search([
                ('meter_number', '=', meter_number),
            ], limit=1)

            if not meter:
                _logger.warning('AMI webhook: meter %s not found', meter_number)
                return Response(
                    json.dumps({'status': 'error', 'message': 'Meter not found'}),
                    status=404,
                    mimetype='application/json',
                )

            event_vals = {
                'event_type': event_type,
                'meter_id': meter.id,
                'account_id': meter.customer_id.id if meter.customer_id else False,
                'event_value': data.get('value', 0.0),
                'event_data': payload.decode() if isinstance(payload, bytes) else payload,
                'raw_payload': payload.decode() if isinstance(payload, bytes) else payload,
                'source': data.get('source', 'ami_webhook'),
                'severity': data.get('severity', 'info'),
            }

            event = request.env['utility.prepaid.ami.event'].sudo().create(event_vals)

            if event_type in ('low_credit', 'zero_credit'):
                event._handle_credit_event()
            elif event_type == 'token_accepted':
                event._handle_token_accepted()
            elif event_type == 'balance_update':
                event._handle_balance_update()

            event.write({
                'processed': True,
                'processed_date': fields.Datetime.now(),
                'processing_result': 'Processed via AMI webhook',
            })

            return Response(
                json.dumps({
                    'status': 'ok',
                    'event_reference': event.reference,
                }),
                status=200,
                mimetype='application/json',
            )

        except Exception as e:
            _logger.exception('AMI webhook processing error for event %s', event_type)
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}),
                status=500,
                mimetype='application/json',
            )
