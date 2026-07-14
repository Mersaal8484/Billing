import json
import logging
import time
import hashlib

from odoo import http, fields, _
from odoo.http import request, Response
from odoo.exceptions import UserError, ValidationError

from ..services.vending_engine import VendingEngine
from ..services.idempotency_service import IdempotencyService
from ..services.notification_engine import NotificationEngine

_logger = logging.getLogger(__name__)

API_PREFIX = '/api/v1/prepaid'
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 100


class PrepaidAPIController(http.Controller):
    """REST API controller for prepaid vending operations.

    All endpoints require API key authentication via header:
    X-API-Key: <api_key>
    """

    def _validate_api_key(self):
        api_key = request.httprequest.headers.get('X-API-Key')
        if not api_key:
            return self._json_response({
                'success': False,
                'error': _('Missing API key. Provide X-API-Key header.'),
            }, status=401)

        api_key_rec = request.env['utility.sts.provider'].sudo().search([
            ('api_key', '=', api_key),
            ('active', '=', True),
        ], limit=1)
        if not api_key_rec:
            return self._json_response({
                'success': False,
                'error': _('Invalid API key.'),
            }, status=401)

        if api_key_rec.health_state == 'down':
            return self._json_response({
                'success': False,
                'error': _('API provider is currently down.'),
            }, status=503)

        return api_key_rec

    def _check_rate_limit(self, key=None):
        cache = request.env.registry.get('cache')
        if not cache:
            return True
        client_ip = request.httprequest.remote_addr
        rate_key = f'prepaid_api_rate:{client_ip}:{key or "global"}'
        try:
            current = cache.get(rate_key) or 0
            if int(current) >= RATE_LIMIT_MAX:
                return False
            cache.set(rate_key, int(current) + 1, expire=RATE_LIMIT_WINDOW)
        except Exception:
            _logger.debug('Rate limit cache unavailable')
        return True

    def _json_response(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False, default=str)
        return Response(payload, status=status, mimetype='application/json')

    def _parse_json(self):
        try:
            return request.get_json_data() or {}
        except Exception:
            return {}

    @http.route(f'{API_PREFIX}/quote', type='http', auth='none', methods=['POST'], csrf=False)
    def api_quote(self):
        api_key = self._validate_api_key()
        if isinstance(api_key, Response):
            return api_key

        if not self._check_rate_limit('quote'):
            return self._json_response({
                'success': False,
                'error': _('Rate limit exceeded. Try again later.'),
            }, status=429)

        data = self._parse_json()
        account_id = data.get('account_id')
        meter_id = data.get('meter_id')
        amount = data.get('amount')

        if not account_id or not meter_id or not amount:
            return self._json_response({
                'success': False,
                'error': _('Required fields: account_id, meter_id, amount'),
            }, status=400)

        try:
            account = request.env['utility.customer'].sudo().browse(int(account_id))
            meter = request.env['utility.meter'].sudo().browse(int(meter_id))

            if not account.exists():
                return self._json_response({
                    'success': False,
                    'error': _('Account not found.'),
                }, status=404)
            if not meter.exists():
                return self._json_response({
                    'success': False,
                    'error': _('Meter not found.'),
                }, status=404)
            if meter.customer_id != account:
                return self._json_response({
                    'success': False,
                    'error': _('Meter does not belong to the specified account.'),
                }, status=400)

            vending_engine = VendingEngine(request.env)
            quote = vending_engine.calculate_vending_quote(
                account=account,
                meter=meter,
                amount=float(amount),
                vending_date=fields.Datetime.now(),
            )

            return self._json_response({
                'success': True,
                'quote': quote,
            })

        except UserError as e:
            return self._json_response({
                'success': False,
                'error': str(e),
            }, status=400)
        except Exception as e:
            _logger.exception('Quote API error')
            return self._json_response({
                'success': False,
                'error': _('Internal server error.'),
            }, status=500)

    @http.route(f'{API_PREFIX}/vending', type='http', auth='none', methods=['POST'], csrf=False)
    def api_vending(self):
        api_key = self._validate_api_key()
        if isinstance(api_key, Response):
            return api_key

        if not self._check_rate_limit('vending'):
            return self._json_response({
                'success': False,
                'error': _('Rate limit exceeded. Try again later.'),
            }, status=429)

        data = self._parse_json()
        idempotency_key = data.get('idempotency_key')

        idempotency_service = IdempotencyService(request.env)
        if idempotency_key:
            existing = idempotency_service.check_idempotency_key(
                request.env.company.id, idempotency_key)
            if existing:
                return self._json_response({
                    'success': True,
                    'existing': True,
                    'reference': existing.reference,
                    'state': existing.state,
                })

        account_id = data.get('account_id')
        meter_id = data.get('meter_id')
        amount = data.get('amount')

        if not account_id or not meter_id or not amount:
            return self._json_response({
                'success': False,
                'error': _('Required fields: account_id, meter_id, amount, idempotency_key'),
            }, status=400)

        try:
            account = request.env['utility.customer'].sudo().browse(int(account_id))
            meter = request.env['utility.meter'].sudo().browse(int(meter_id))

            vending_engine = VendingEngine(request.env)
            quote = vending_engine.calculate_vending_quote(
                account=account,
                meter=meter,
                amount=float(amount),
            )

            quote['account_id'] = account.id
            quote['meter_id'] = meter.id

            payment_data = {
                'idempotency_key': idempotency_key,
                'operator_id': request.env.user.id if request.env.user.id != 1 else False,
                'channel_id': data.get('channel_id'),
                'notes': data.get('notes'),
            }

            vending_request = vending_engine.create_vending_request(quote, payment_data)
            vending_request.action_quote()

            return self._json_response({
                'success': True,
                'reference': vending_request.reference,
                'state': vending_request.state,
                'quote': quote,
            }, status=201)

        except UserError as e:
            return self._json_response({
                'success': False,
                'error': str(e),
            }, status=400)
        except Exception as e:
            _logger.exception('Vending API error')
            return self._json_response({
                'success': False,
                'error': _('Internal server error.'),
            }, status=500)

    @http.route(f'{API_PREFIX}/vending/payment', type='http', auth='none', methods=['POST'], csrf=False)
    def api_vending_payment(self):
        api_key = self._validate_api_key()
        if isinstance(api_key, Response):
            return api_key

        data = self._parse_json()
        reference = data.get('reference')

        if not reference:
            return self._json_response({
                'success': False,
                'error': _('Required field: reference'),
            }, status=400)

        try:
            vending_request = request.env['utility.vending.request'].sudo().search([
                ('reference', '=', reference),
            ], limit=1)

            if not vending_request:
                return self._json_response({
                    'success': False,
                    'error': _('Vending request not found.'),
                }, status=404)

            vending_engine = VendingEngine(request.env)
            vending_engine.confirm_payment(vending_request)

            return self._json_response({
                'success': True,
                'reference': vending_request.reference,
                'state': vending_request.state,
                'paid_date': vending_request.paid_date,
            })

        except UserError as e:
            return self._json_response({
                'success': False,
                'error': str(e),
            }, status=400)
        except Exception as e:
            _logger.exception('Vending payment API error')
            return self._json_response({
                'success': False,
                'error': _('Internal server error.'),
            }, status=500)

    @http.route(f'{API_PREFIX}/vending/<string:reference>', type='http', auth='none', methods=['GET'], csrf=False)
    def api_vending_status(self, reference):
        api_key = self._validate_api_key()
        if isinstance(api_key, Response):
            return api_key

        try:
            vending_request = request.env['utility.vending.request'].sudo().search([
                ('reference', '=', reference),
            ], limit=1)

            if not vending_request:
                return self._json_response({
                    'success': False,
                    'error': _('Vending request not found.'),
                }, status=404)

            tokens = vending_request.token_ids.filtered(lambda t: t.status == 'success')
            token_data = []
            for token in tokens:
                token_data.append({
                    'token_number': token.mask_display,
                    'kwh': token.kwh,
                    'amount': token.amount,
                    'status': token.status,
                    'delivery_state': token.delivery_state,
                })

            return self._json_response({
                'success': True,
                'reference': vending_request.reference,
                'state': vending_request.state,
                'gross_amount': vending_request.gross_amount,
                'energy_amount': vending_request.energy_amount,
                'kwh_purchased': vending_request.kwh_purchased,
                'tokens': token_data,
                'vending_date': vending_request.vending_date,
                'completed_date': vending_request.completed_date,
            })

        except Exception as e:
            _logger.exception('Vending status API error')
            return self._json_response({
                'success': False,
                'error': _('Internal server error.'),
            }, status=500)

    @http.route(f'{API_PREFIX}/vending/<string:reference>/retry', type='http', auth='none', methods=['POST'], csrf=False)
    def api_vending_retry(self, reference):
        api_key = self._validate_api_key()
        if isinstance(api_key, Response):
            return api_key

        try:
            vending_request = request.env['utility.vending.request'].sudo().search([
                ('reference', '=', reference),
            ], limit=1)

            if not vending_request:
                return self._json_response({
                    'success': False,
                    'error': _('Vending request not found.'),
                }, status=404)

            if vending_request.state not in ('token_pending', 'token_failed'):
                return self._json_response({
                    'success': False,
                    'error': _('Can only retry requests in token_pending or token_failed state.'),
                }, status=400)

            idempotency_service = IdempotencyService(request.env)
            result = idempotency_service.handle_pending_request(vending_request)

            return self._json_response({
                'success': True,
                'reference': vending_request.reference,
                'state': vending_request.state,
                'retry_result': result,
            })

        except UserError as e:
            return self._json_response({
                'success': False,
                'error': str(e),
            }, status=400)
        except Exception as e:
            _logger.exception('Vending retry API error')
            return self._json_response({
                'success': False,
                'error': _('Internal server error.'),
            }, status=500)

    @http.route(f'{API_PREFIX}/vending/<string:reference>/resend', type='http', auth='none', methods=['POST'], csrf=False)
    def api_vending_resend(self, reference):
        api_key = self._validate_api_key()
        if isinstance(api_key, Response):
            return api_key

        try:
            vending_request = request.env['utility.vending.request'].sudo().search([
                ('reference', '=', reference),
            ], limit=1)

            if not vending_request:
                return self._json_response({
                    'success': False,
                    'error': _('Vending request not found.'),
                }, status=404)

            token = vending_request.token_ids.filtered(
                lambda t: t.status == 'success', limit=1)
            if not token:
                return self._json_response({
                    'success': False,
                    'error': _('No successful token found for this vending request.'),
                }, status=400)

            notification_engine = NotificationEngine(request.env)
            sent = notification_engine.send_token_notification(token, method='sms')

            if sent:
                token.action_resend_sms()
                return self._json_response({
                    'success': True,
                    'message': _('Token resent successfully via SMS.'),
                    'resend_count': token.resend_count,
                })
            else:
                return self._json_response({
                    'success': False,
                    'error': _('Failed to resend token.'),
                }, status=500)

        except UserError as e:
            return self._json_response({
                'success': False,
                'error': str(e),
            }, status=400)
        except Exception as e:
            _logger.exception('Vending resend API error')
            return self._json_response({
                'success': False,
                'error': _('Internal server error.'),
            }, status=500)

    @http.route(f'{API_PREFIX}/vending/<string:reference>/reversal', type='http', auth='none', methods=['POST'], csrf=False)
    def api_vending_reversal(self, reference):
        api_key = self._validate_api_key()
        if isinstance(api_key, Response):
            return api_key

        data = self._parse_json()
        reason_id = data.get('reason_id')
        reversal_type = data.get('reversal_type', 'full')

        if not reason_id:
            return self._json_response({
                'success': False,
                'error': _('Required field: reason_id'),
            }, status=400)

        try:
            vending_request = request.env['utility.vending.request'].sudo().search([
                ('reference', '=', reference),
            ], limit=1)

            if not vending_request:
                return self._json_response({
                    'success': False,
                    'error': _('Vending request not found.'),
                }, status=404)

            if vending_request.state not in ('completed', 'token_generated'):
                return self._json_response({
                    'success': False,
                    'error': _('Can only reverse completed or token_generated requests.'),
                }, status=400)

            reason = request.env['utility.reversal.reason'].sudo().browse(int(reason_id))
            if not reason.exists():
                return self._json_response({
                    'success': False,
                    'error': _('Reversal reason not found.'),
                }, status=404)

            token = vending_request.token_ids.filtered(
                lambda t: t.status == 'success', limit=1)

            reversal = request.env['utility.vending.reversal'].sudo().create({
                'vending_request_id': vending_request.id,
                'token_id': token.id if token else False,
                'reversal_type': reversal_type,
                'amount': vending_request.energy_amount,
                'reason_id': reason.id,
                'reason_details': data.get('notes', ''),
            })
            reversal.action_submit()

            return self._json_response({
                'success': True,
                'reversal_reference': reversal.reference,
                'state': reversal.state,
            }, status=201)

        except UserError as e:
            return self._json_response({
                'success': False,
                'error': str(e),
            }, status=400)
        except Exception as e:
            _logger.exception('Vending reversal API error')
            return self._json_response({
                'success': False,
                'error': _('Internal server error.'),
            }, status=500)

    @http.route(f'{API_PREFIX}/ami/event', type='http', auth='none', methods=['POST'], csrf=False)
    def api_ami_event(self):
        api_key = self._validate_api_key()
        if isinstance(api_key, Response):
            return api_key

        data = self._parse_json()
        event_type = data.get('event_type')
        meter_number = data.get('meter_number')

        if not event_type or not meter_number:
            return self._json_response({
                'success': False,
                'error': _('Required fields: event_type, meter_number'),
            }, status=400)

        try:
            meter = request.env['utility.meter'].sudo().search([
                ('meter_number', '=', meter_number),
            ], limit=1)

            if not meter:
                return self._json_response({
                    'success': False,
                    'error': _('Meter not found.'),
                }, status=404)

            account = meter.customer_id

            event_vals = {
                'event_type': event_type,
                'meter_id': meter.id,
                'account_id': account.id if account else False,
                'event_value': data.get('event_value', 0.0),
                'event_data': json.dumps(data, ensure_ascii=False),
                'raw_payload': json.dumps(data, ensure_ascii=False),
                'source': data.get('source', 'api'),
                'severity': data.get('severity', 'info'),
            }

            event = request.env['utility.prepaid.ami.event'].sudo().create(event_vals)

            if data.get('process_immediately'):
                event.action_process()

            return self._json_response({
                'success': True,
                'event_reference': event.reference,
                'processed': event.processed,
            })

        except UserError as e:
            return self._json_response({
                'success': False,
                'error': str(e),
            }, status=400)
        except Exception as e:
            _logger.exception('AMI event API error')
            return self._json_response({
                'success': False,
                'error': _('Internal server error.'),
            }, status=500)

    @http.route(f'{API_PREFIX}/sts/callback', type='http', auth='none', methods=['POST'], csrf=False)
    def api_sts_callback(self):
        api_key = self._validate_api_key()
        if isinstance(api_key, Response):
            return api_key

        data = self._parse_json()
        provider_reference = data.get('provider_reference')
        token_value = data.get('token_value')
        state = data.get('state')

        if not provider_reference:
            return self._json_response({
                'success': False,
                'error': _('Required field: provider_reference'),
            }, status=400)

        try:
            sts_tx = request.env['utility.sts.transaction'].sudo().search([
                ('provider_reference', '=', provider_reference),
                ('state', 'in', ('pending', 'sent')),
            ], limit=1)

            if not sts_tx:
                return self._json_response({
                    'success': False,
                    'error': _('STS transaction not found.'),
                }, status=404)

            if state == 'success' and token_value:
                sts_tx.write({
                    'state': 'success',
                    'token_value': token_value,
                    'token_identifier': data.get('token_identifier'),
                    'response_date': fields.Datetime.now(),
                    'response_code': data.get('response_code', '00'),
                    'response_message': data.get('response_message', ''),
                    'raw_response': json.dumps(data, ensure_ascii=False),
                })

                vending_req = sts_tx.vending_request_id
                if vending_req:
                    request.env['utility.token'].sudo().create({
                        'vending_request_id': vending_req.id,
                        'account_id': vending_req.account_id.id,
                        'meter_id': vending_req.meter_id.id,
                        'customer_id': vending_req.partner_id.id,
                        'token_number': token_value,
                        'token_identifier': data.get('token_identifier'),
                        'amount': vending_req.energy_amount,
                        'kwh': vending_req.kwh_purchased,
                        'status': 'success',
                        'response_date': fields.Datetime.now(),
                        'response_code': '00',
                        'response_message': _('Token generated successfully via STS callback'),
                        'sts_server': sts_tx.provider_id.name,
                        'provider_reference': provider_reference,
                    })
                    vending_req.write({'state': 'token_generated'})

            elif state == 'failed':
                sts_tx.write({
                    'state': 'failed',
                    'error_code': data.get('error_code', 'CALLBACK_ERROR'),
                    'error_message': data.get('error_message', 'STS callback reported failure'),
                    'response_date': fields.Datetime.now(),
                    'raw_response': json.dumps(data, ensure_ascii=False),
                })
                vending_req = sts_tx.vending_request_id
                if vending_req:
                    vending_req.write({
                        'state': 'token_failed',
                        'last_error': data.get('error_message', 'STS callback reported failure'),
                    })

            return self._json_response({
                'success': True,
                'message': _('STS callback processed.'),
            })

        except UserError as e:
            return self._json_response({
                'success': False,
                'error': str(e),
            }, status=400)
        except Exception as e:
            _logger.exception('STS callback API error')
            return self._json_response({
                'success': False,
                'error': _('Internal server error.'),
            }, status=500)
