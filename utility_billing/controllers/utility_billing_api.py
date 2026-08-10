from odoo import fields, http
from odoo.http import request
import hmac
import logging

_logger = logging.getLogger(__name__)


class UtilityBillingAPI(http.Controller):

    def _get_authorized_accounts(self):
        """إرجاع recordset لحسابات الكهرباء المسموح للمستخدم الحالي الوصول إليها.

        للمستخدمين الداخليين: كل الحسابات.
        لمستخدمي البوابة: الحسابات المرتبطة بـ partner الخاص بهم فقط.
        """
        user = request.env.user
        Customer = request.env['utility.customer']
        if user.has_group('base.group_user'):
            # Internal calls deliberately use the normal environment so ACLs
            # and ir.rules remain the single authorization source of truth.
            return Customer.search([])
        return Customer.sudo().search([
            ('partner_id', '=', user.partner_id.id),
        ])

    def _authorize_account(self, customer_number):
        """التحقق من ملكية حساب الكهرباء وإرجاعه إن وجد."""
        accounts = self._get_authorized_accounts()
        return accounts.filtered(lambda a: a.customer_number == customer_number)[:1]

    def _authorize_order(self, order_id):
        """التحقق من ملكية الفاتورة وإرجاعها إن وجدت."""
        user = request.env.user
        try:
            order_id = int(order_id)
        except (TypeError, ValueError):
            return request.env['sale.order']
        Order = request.env['sale.order'] if user.has_group('base.group_user') else request.env['sale.order'].sudo()
        order = Order.browse(order_id)
        if not order.exists():
            return Order
        if order.customer_id in self._get_authorized_accounts():
            return order
        return Order.browse()

    @http.route('/api/v1/utility/billing/balance', type='json', auth='user', methods=['POST'])
    def billing_balance(self, **kwargs):
        params = request.jsonrequest
        customer_number = params.get('customer_number')
        if not customer_number:
            return {'error': 'customer_number is required'}
        account = self._authorize_account(customer_number)
        if not account:
            return {'error': 'Account not found'}
        orders = request.env['sale.order'].sudo().search([
            ('customer_id', '=', account.id),
            ('bill_state', 'not in', ('paid', 'cancelled')),
        ])
        debt = sum(orders.mapped('balance_due'))
        return {
            'customer_number': account.customer_number,
            'accounting_balance': account.accounting_balance,
            'debt': debt,
            'last_purchase_date': account.last_purchase_date.isoformat() if account.last_purchase_date else None,
        }

    @http.route('/api/v1/utility/billing/bills', type='json', auth='user', methods=['POST'])
    def billing_bills(self, **kwargs):
        params = request.jsonrequest
        customer_number = params.get('customer_number')
        limit = params.get('limit', 12)
        if not customer_number:
            return {'error': 'customer_number is required'}
        account = self._authorize_account(customer_number)
        if not account:
            return {'error': 'Account not found'}
        orders = request.env['sale.order'].sudo().search([
            ('customer_id', '=', account.id),
        ], order='date_order desc', limit=limit)
        return {
            'bills': [{
                'bill_number': o.name,
                'period': '%s - %s' % (o.period_start, o.period_end) if o.period_start and o.period_end else None,
                'amount': o.amount_total,
                'paid': o.amount_paid,
                'balance': o.balance_due,
                'due_date': o.date_order.date().isoformat() if o.date_order else None,
                'state': o.bill_state,
            } for o in orders],
        }

    @http.route('/api/v1/utility/billing/pay', type='json', auth='user', methods=['POST'])
    def billing_pay(self, **kwargs):
        """تم تعطيل الدفع المباشر من البوابة. استخدم /api/v1/utility/billing/payment_intent بدلاً منه."""
        return {
            'error': 'Direct payment creation is disabled. Use /api/v1/utility/billing/payment_intent instead.',
        }

    @http.route('/api/v1/utility/billing/payment_intent', type='json', auth='user', methods=['POST'])
    def billing_payment_intent(self, **kwargs):
        params = request.jsonrequest
        order_id = params.get('order_id')
        amount = params.get('amount')
        provider_id = params.get('provider_id')
        invoice_id = params.get('invoice_id')
        direction = params.get('payment_direction', 'inbound')
        if direction != 'inbound':
            return {'error': 'Customer payment intents support inbound payments only'}

        if not order_id or not amount:
            return {'error': 'order_id and amount are required'}
        order = self._authorize_order(order_id)
        if not order:
            return {'error': 'Order not found'}
        posted_moves = order._get_posted_utility_moves()
        if invoice_id:
            try:
                invoice_id = int(invoice_id)
            except (TypeError, ValueError):
                return {'error': 'invoice_id must be numeric'}
            invoice = request.env['account.move'].sudo().browse(invoice_id).exists()
            if (not invoice or len(invoice) != 1 or invoice not in posted_moves
                    or invoice.partner_id != order.partner_id):
                return {'error': 'invoice_id must identify a posted accounting invoice of this bill'}
        elif len(posted_moves) == 1:
            invoice = posted_moves
        else:
            return {'error': 'invoice_id is required when the bill has multiple accounting invoices'}
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return {'error': 'amount must be a positive number'}
        if amount <= 0:
            return {'error': 'amount must be a positive number'}

        if direction == 'inbound':
            if amount > invoice.amount_residual:
                return {'error': 'amount cannot exceed the selected invoice residual'}
            if order.bill_state in ('paid', 'cancelled'):
                return {'error': 'Bill is not payable'}

        Provider = request.env['utility.integration.provider'].sudo()
        if provider_id:
            provider = Provider.browse(int(provider_id))
        else:
            provider = Provider.search([
                ('is_payment_capable', '=', True),
                ('payment_direction', 'in', (direction, 'both')),
                ('active', '=', True),
                ('company_id', '=', order.company_id.id),
            ], limit=1)

        if not provider or not provider.active or not provider.is_payment_capable:
            return {'error': 'No active payment provider configured for the requested operation'}
        if not provider.supports_direction(direction):
            return {'error': 'Provider %s does not support payment direction: %s' % (provider.name, direction)}
        if provider.company_id and provider.company_id != order.company_id:
            return {'error': 'Payment provider is not available for the bill company'}

        tx = request.env['utility.payment.gateway.transaction'].sudo().create({
            'provider_id': provider.id,
            'payment_direction': direction,
            'sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'amount': amount,
        })
        tx.action_mark_pending()
        return {
            'transaction_id': tx.id,
            'reference': tx.name,
            'payment_direction': tx.payment_direction,
            'state': tx.state,
            'amount': tx.amount,
        }

    @http.route('/api/v1/utility/payment_gateway/webhook/<string:reference>', type='json', auth='public', methods=['POST'], csrf=False)
    def payment_gateway_webhook(self, reference, **kwargs):
        params = request.jsonrequest or {}
        tx = request.env['utility.payment.gateway.transaction'].sudo().search([
            ('name', '=', reference),
        ], limit=1)
        if not tx:
            return {'error': 'Transaction not found'}
        token = params.get('token') or params.get('callback_token') or params.get('signature')
        if not token or not tx.access_token:
            _logger.warning('Payment webhook missing token for reference %s', reference)
            return {'error': 'Missing authentication token'}
        expected = tx.access_token.encode('utf-8')
        received = token.encode('utf-8')
        if len(expected) != len(received) or not hmac.compare_digest(expected, received):
            _logger.warning('Payment webhook invalid token for reference %s', reference)
            return {'error': 'Invalid token'}
        status = params.get('status')
        if not status:
            return {'error': 'Payment status is required'}
        provider_reference = params.get('provider_reference') or params.get('reference')
        if tx.state == 'done':
            return {'success': True, 'state': tx.state, 'payment_id': tx.payment_id.id}
        if tx.state != 'pending':
            return {'error': 'Only pending payment transactions can receive callbacks'}
        if status in ('success', 'done', 'paid') and not provider_reference:
            return {'error': 'Provider reference is required for successful payments'}
        if status not in ('success', 'done', 'paid'):
            tx.write({
                'state': 'failed',
                'callback_payload': str(params),
                'error_message': params.get('error') or 'Payment gateway reported failure',
            })
            return {'success': False, 'state': tx.state}
        tx.action_confirm_payment(provider_reference=provider_reference, callback_payload=str(params))
        return {'success': True, 'state': tx.state, 'payment_id': tx.payment_id.id}

    @http.route('/api/v1/utility/operations/service_request', type='json', auth='user', methods=['POST'])
    def service_request(self, **kwargs):
        params = request.jsonrequest
        customer_id = params.get('customer_id')
        service_type = params.get('service_type')
        description = params.get('description')
        if not customer_id or not service_type or not description:
            return {'error': 'customer_id, service_type, and description are required'}
        try:
            customer_id = int(customer_id)
        except (TypeError, ValueError):
            return {'error': 'customer_id must be numeric'}
        account = request.env['utility.customer'].sudo().browse(customer_id)
        if not account.exists():
            return {'error': 'Customer account not found'}
        if account not in self._get_authorized_accounts():
            return {'error': 'Customer account not found'}
        try:
            order = request.env['utility.service.order'].sudo().create({
                'customer_id': customer_id,
                'service_type': service_type,
                'description': description,
                'state': 'draft',
            })
            return {'order_number': order.order_number}
        except KeyError:
            return {'error': 'utility.service.order model not available'}

    @http.route('/api/v1/utility/ami/reading_callback', type='json', auth='public', methods=['POST'], csrf=False)
    def ami_reading_callback(self, **kwargs):
        params = request.jsonrequest or {}
        secret = params.get('secret') or params.get('webhook_secret')
        if not secret:
            return {'error': 'webhook secret is required'}
        provider = request.env['utility.integration.provider'].sudo().search([
            ('provider_type', '=', 'ami'),
            ('active', '=', True),
            ('webhook_secret', '=', secret),
        ], limit=1)
        if not provider:
            return {'error': 'Invalid AMI provider secret'}
        meter_number = params.get('meter_number')
        reading_value = params.get('reading_value')
        if not meter_number or reading_value is None:
            return {'error': 'meter_number and reading_value are required'}
        meter = request.env['utility.meter'].sudo().search([('meter_number', '=', meter_number)], limit=1)
        if not meter:
            return {'error': 'Meter not found'}
        if meter.company_id != provider.company_id:
            return {'error': 'Meter is not available for this AMI provider company'}
        try:
            reading_value = float(reading_value)
        except (TypeError, ValueError):
            return {'error': 'reading_value must be numeric'}
        date_range_id = params.get('date_range_id') or False
        if date_range_id:
            try:
                date_range_id = int(date_range_id)
            except (TypeError, ValueError):
                return {'error': 'date_range_id must be numeric'}
            period = request.env['date.range'].sudo().browse(date_range_id).exists()
            if (not period or period.company_id not in (False, provider.company_id)
                    or period.period_role != 'reading'
                    or period.state != 'open'):
                return {'error': 'Invalid reading period for this AMI provider company'}
        reading = meter.create_ami_reading(
            reading_value,
            reading_date=params.get('reading_date') or False,
            date_range_id=date_range_id or False,
        )
        provider.call_json({
            'meter_number': meter_number,
            'reading_id': reading.reading_id,
            'reading_value': reading_value,
        }, 'ami.reading.callback', record=reading)
        return {'success': True, 'reading_id': reading.id, 'reading_number': reading.reading_id}

    @http.route('/api/v1/utility/reports/daily', type='json', auth='user', methods=['POST'])
    def reports_daily(self, **kwargs):
        from datetime import date
        params = request.jsonrequest
        report_date = params.get('date', date.today().isoformat())
        region_id = params.get('region_id')
        area_id = params.get('area_id')
        user = request.env.user
        if not user.has_group('base.group_user'):
            return {'error': 'Access denied. Reports are for internal users only.'}
        allowed_accounts = self._get_authorized_accounts()
        allowed_ids = allowed_accounts.ids
        if not allowed_ids:
            return {'total_bills': 0, 'total_collections': 0.0, 'active_alarms': 0}
        start_dt = '%s 00:00:00' % report_date
        end_dt = '%s 23:59:59' % report_date

        bills_domain = [
            ('customer_id', 'in', allowed_ids),
            ('date_order', '>=', start_dt),
            ('date_order', '<=', end_dt),
        ]
        if region_id:
            bills_domain.append(('customer_id.region_id', '=', int(region_id)))
        if area_id:
            bills_domain.append(('customer_id.area_id', '=', int(area_id)))
        total_bills = request.env['sale.order'].search_count(bills_domain)

        payments_domain = [
            ('date', '=', report_date),
            ('utility_sale_order_id.customer_id', 'in', allowed_ids),
        ]
        pay_data = request.env['account.payment'].read_group(
            payments_domain, ['amount:sum'], [])
        total_collections = pay_data[0].get('amount', 0) if pay_data else 0.0

        alarms_domain = [
            ('customer_id', 'in', allowed_ids),
            ('alarm_date', '>=', start_dt), ('alarm_date', '<=', end_dt),
            ('state', 'not in', ('resolved', 'closed')),
        ]
        active_alarms = request.env['utility.alarm'].search_count(alarms_domain)

        return {
            'total_bills': total_bills,
            'total_collections': total_collections,
            'active_alarms': active_alarms,
        }
