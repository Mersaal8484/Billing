import logging

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import UserError, AccessError

from ..services.vending_engine import VendingEngine
from ..services.idempotency_service import IdempotencyService

_logger = logging.getLogger(__name__)


class PrepaidPortalController(http.Controller):
    """Portal controller for customer self-service prepaid operations."""

    def _prepare_portal_values(self):
        partner = request.env.user.partner_id
        return {
            'partner': partner,
            'company': request.env.company,
        }

    @http.route('/my/prepaid', type='http', auth='user', website=True)
    def portal_prepaid_dashboard(self, **kw):
        partner = request.env.user.partner_id
        accounts = request.env['utility.customer'].search([
            ('partner_id', '=', partner.id),
        ])

        vending_requests = request.env['utility.vending.request'].search([
            ('partner_id', '=', partner.id),
        ], limit=10, order='create_date desc')

        tokens = request.env['utility.token'].search([
            ('customer_id', '=', partner.id),
            ('status', '=', 'success'),
        ], limit=5, order='create_date desc')

        return request.render('utility_prepaid.portal_prepaid_dashboard', {
            'accounts': accounts,
            'vending_requests': vending_requests,
            'tokens': tokens,
            'page_name': 'prepaid_dashboard',
        })

    @http.route('/my/prepaid/accounts', type='http', auth='user', website=True)
    def portal_prepaid_accounts(self, **kw):
        partner = request.env.user.partner_id
        accounts = request.env['utility.customer'].search([
            ('partner_id', '=', partner.id),
        ])

        return request.render('utility_prepaid.portal_prepaid_accounts', {
            'accounts': accounts,
            'page_name': 'prepaid_accounts',
        })

    @http.route('/my/prepaid/account/<model("utility.customer"):account>', type='http', auth='user', website=True)
    def portal_prepaid_account_detail(self, account, **kw):
        partner = request.env.user.partner_id
        if account.partner_id != partner:
            raise AccessError(_('You do not have access to this account.'))

        vending_requests = request.env['utility.vending.request'].search([
            ('account_id', '=', account.id),
        ], order='create_date desc', limit=20)

        tokens = request.env['utility.token'].search([
            ('account_id', '=', account.id),
        ], order='create_date desc', limit=10)

        meter = account.meter_ids[:1] if hasattr(account, 'meter_ids') else False

        return request.render('utility_prepaid.portal_prepaid_account_detail', {
            'account': account,
            'meter': meter,
            'vending_requests': vending_requests,
            'tokens': tokens,
            'page_name': 'prepaid_account_detail',
        })

    @http.route('/my/prepaid/vending/new', type='http', auth='user', website=True)
    def portal_vending_new(self, account_id=None, **kw):
        partner = request.env.user.partner_id
        accounts = request.env['utility.customer'].search([
            ('partner_id', '=', partner.id),
        ])

        selected_account = None
        meters = request.env['utility.meter']

        if account_id:
            selected_account = request.env['utility.customer'].browse(int(account_id))
            if selected_account.partner_id != partner:
                raise AccessError(_('You do not have access to this account.'))
            if hasattr(selected_account, 'meter_ids'):
                meters = selected_account.meter_ids

        return request.render('utility_prepaid.portal_vending_new', {
            'accounts': accounts,
            'selected_account': selected_account,
            'meters': meters,
            'page_name': 'vending_new',
        })

    @http.route('/my/prepaid/vending/quote', type='json', auth='user')
    def portal_vending_quote(self, account_id, meter_id, amount, **kw):
        partner = request.env.user.partner_id

        try:
            account = request.env['utility.customer'].browse(int(account_id))
            meter = request.env['utility.meter'].browse(int(meter_id))

            if account.partner_id != partner:
                raise UserError(_('You do not have access to this account.'))
            if meter.customer_id != account:
                raise UserError(_('Meter does not belong to the selected account.'))
            if not amount or float(amount) <= 0:
                raise UserError(_('Amount must be greater than zero.'))

            vending_engine = VendingEngine(request.env)
            quote = vending_engine.calculate_vending_quote(
                account=account,
                meter=meter,
                amount=float(amount),
            )

            return {
                'success': True,
                'quote': quote,
            }

        except UserError as e:
            return {
                'success': False,
                'error': str(e),
            }
        except Exception as e:
            _logger.exception('Portal vending quote error')
            return {
                'success': False,
                'error': _('An error occurred while calculating the quote.'),
            }

    @http.route('/my/prepaid/vending/submit', type='json', auth='user')
    def portal_vending_submit(self, account_id, meter_id, amount, **kw):
        partner = request.env.user.partner_id

        try:
            account = request.env['utility.customer'].browse(int(account_id))
            meter = request.env['utility.meter'].browse(int(meter_id))

            if account.partner_id != partner:
                raise UserError(_('You do not have access to this account.'))
            if meter.customer_id != account:
                raise UserError(_('Meter does not belong to the selected account.'))

            vending_engine = VendingEngine(request.env)
            quote = vending_engine.calculate_vending_quote(
                account=account,
                meter=meter,
                amount=float(amount),
            )

            quote['account_id'] = account.id
            quote['meter_id'] = meter.id

            idempotency_service = IdempotencyService(request.env)
            idempotency_key = idempotency_service.generate_idempotency_key(
                account, meter, float(amount))

            existing = idempotency_service.check_idempotency_key(
                request.env.company.id, idempotency_key)
            if existing:
                return {
                    'success': True,
                    'existing': True,
                    'reference': existing.reference,
                    'state': existing.state,
                }

            payment_data = {
                'idempotency_key': idempotency_key,
                'channel_id': kw.get('channel_id'),
                'notes': kw.get('notes'),
            }

            vending_request = vending_engine.create_vending_request(quote, payment_data)
            vending_request.action_quote()

            return {
                'success': True,
                'reference': vending_request.reference,
                'state': vending_request.state,
                'redirect': f'/my/prepaid/vending/{vending_request.reference}',
            }

        except UserError as e:
            return {
                'success': False,
                'error': str(e),
            }
        except Exception as e:
            _logger.exception('Portal vending submit error')
            return {
                'success': False,
                'error': _('An error occurred while submitting the vending request.'),
            }

    @http.route('/my/prepaid/vending/<string:reference>', type='http', auth='user', website=True)
    def portal_vending_status(self, reference, **kw):
        partner = request.env.user.partner_id

        vending_request = request.env['utility.vending.request'].search([
            ('reference', '=', reference),
            ('partner_id', '=', partner.id),
        ], limit=1)

        if not vending_request:
            return request.redirect('/my/prepaid')

        tokens = vending_request.token_ids.filtered(lambda t: t.status == 'success')

        return request.render('utility_prepaid.portal_vending_status', {
            'vending_request': vending_request,
            'tokens': tokens,
            'page_name': 'vending_status',
        })

    @http.route('/my/prepaid/token/<model("utility.token"):token>', type='http', auth='user', website=True)
    def portal_token_detail(self, token, **kw):
        partner = request.env.user.partner_id
        if token.customer_id != partner:
            raise AccessError(_('You do not have access to this token.'))

        return request.render('utility_prepaid.portal_token_detail', {
            'token': token,
            'page_name': 'token_detail',
        })

    @http.route('/my/prepaid/history', type='http', auth='user', website=True)
    def portal_vending_history(self, page=1, **kw):
        partner = request.env.user.partner_id

        domain = [('partner_id', '=', partner.id)]
        search = kw.get('search', '')
        if search:
            domain.append(('reference', 'ilike', search))

        state_filter = kw.get('state')
        if state_filter:
            domain.append(('state', '=', state_filter))

        date_from = kw.get('date_from')
        if date_from:
            domain.append(('vending_date', '>=', date_from))

        date_to = kw.get('date_to')
        if date_to:
            domain.append(('vending_date', '<=', date_to))

        vending_requests = request.env['utility.vending.request'].search(
            domain,
            order='create_date desc',
            limit=20,
            offset=(int(page) - 1) * 20,
        )

        total = request.env['utility.vending.request'].search_count(domain)

        return request.render('utility_prepaid.portal_vending_history', {
            'vending_requests': vending_requests,
            'total': total,
            'page': int(page),
            'page_name': 'vending_history',
            'search': search,
            'state_filter': state_filter,
            'date_from': date_from,
            'date_to': date_to,
            'states': request.env['utility.vending.request']._fields['state'].selection,
        })

    @http.route('/my/prepaid/token/resend', type='json', auth='user')
    def portal_token_resend(self, token_id, **kw):
        partner = request.env.user.partner_id

        try:
            token = request.env['utility.token'].browse(int(token_id))
            if token.customer_id != partner:
                raise UserError(_('You do not have access to this token.'))
            if token.status != 'success':
                raise UserError(_('Can only resend successful tokens.'))

            limit = request.env.company.token_resend_limit or 5
            if token.resend_count >= limit:
                raise UserError(_('Resend limit (%d) has been reached.') % limit)

            token.action_resend_sms()

            return {
                'success': True,
                'message': _('Token has been resent via SMS.'),
                'resend_count': token.resend_count,
            }

        except UserError as e:
            return {
                'success': False,
                'error': str(e),
            }
        except Exception as e:
            _logger.exception('Portal token resend error')
            return {
                'success': False,
                'error': _('An error occurred while resending the token.'),
            }
