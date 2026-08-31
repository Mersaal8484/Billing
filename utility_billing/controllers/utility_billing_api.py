from odoo import fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
import hmac
import logging
from psycopg2 import IntegrityError
from odoo.addons.utility_core.models.utility_integration import sanitize_sensitive_payload

_logger = logging.getLogger(__name__)


class UtilityBillingAPI(http.Controller):

    @staticmethod
    def _error(code, message):
        """Return the stable API error envelope for all billing endpoints."""
        return {'success': False, 'code': code, 'error': message}

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

    def _resolve_authorized_customer(self, params):
        """Resolve exact customer identifiers within the caller's access scope."""
        accounts = self._get_authorized_accounts()
        customer, error_code = accounts._resolve_identifiers(
            customer_id=params.get('customer_id'),
            customer_number=params.get('customer_number'),
            external_qr_reference=params.get('external_qr_reference'),
            scope_ids=accounts.ids,
        )
        return customer, error_code

    @staticmethod
    def _customer_payload(customer):
        return {
            'customer_id': customer.id,
            'customer_number': customer.customer_number,
            'external_qr_reference': customer.external_qr_reference or None,
            'customer_name': customer.partner_id.name if customer.partner_id else None,
        }

    @http.route('/api/v1/utility/customer/lookup', type='json', auth='user', methods=['POST'])
    def customer_lookup(self, **kwargs):
        """Resolve an authorized customer by exact business identifier."""
        customer, error_code = self._resolve_authorized_customer(request.jsonrequest or {})
        if error_code == 'CUSTOMER_IDENTIFIER_MISMATCH':
            return self._error(error_code, 'معرفات الحساب متعارضة')
        if error_code == 'CUSTOMER_IDENTIFIER_REQUIRED':
            return self._error(
                error_code,
                'customer_id, customer_number or external_qr_reference is required',
            )
        if not customer:
            return self._error(error_code or 'CUSTOMER_NOT_FOUND', 'الحساب غير موجود')
        return {'success': True, 'customer': self._customer_payload(customer)}

    @http.route('/api/v1/utility/customer/qr_reference', type='json', auth='user', methods=['POST'])
    def update_customer_qr_reference(self, **kwargs):
        """Assign or change the current external QR reference idempotently."""
        params = request.jsonrequest or {}
        customer, error_code = self._resolve_authorized_customer(params)
        if error_code == 'CUSTOMER_IDENTIFIER_MISMATCH':
            return self._error(error_code, 'معرفات الحساب متعارضة')
        if error_code == 'CUSTOMER_IDENTIFIER_REQUIRED':
            return self._error(
                error_code,
                'customer_id, customer_number or external_qr_reference is required',
            )
        if not customer:
            return self._error(error_code or 'CUSTOMER_NOT_FOUND', 'الحساب غير موجود')
        target_key = (
            'new_external_qr_reference'
            if 'new_external_qr_reference' in params
            else 'external_qr_reference'
        )
        if target_key not in params:
            return self._error('VALIDATION_ERROR', 'external_qr_reference is required')

        reference = (params.get(target_key) or '').strip() or False
        owner = request.env['utility.customer']
        if reference:
            owner = owner.search([
                ('external_qr_reference', '=', reference),
                ('company_id', '=', customer.company_id.id),
                ('id', '!=', customer.id),
        ], limit=1)
        if owner:
            return self._error(
                'QR_REFERENCE_ALREADY_ASSIGNED',
                'معرف QR الخارجي مستخدم بالفعل لدى حساب آخر',
            )
        try:
            with request.env.cr.savepoint():
                customer.write({'external_qr_reference': reference})
        except IntegrityError:
            return self._error(
                'QR_REFERENCE_ALREADY_ASSIGNED',
                'معرف QR الخارجي مستخدم بالفعل لدى حساب آخر',
            )
        return {'success': True, 'customer': self._customer_payload(customer)}

    def _authorize_order(self, order_id):
        """التحقق من ملكية الفاتورة وإرجاعها ضمن نطاق المستخدم المصرح له.

        للمستخدمين الداخليين تُطبّق Record Rules تلقائياً عبر بيئة ORM العادية،
        ويُضاف شرط ملكية الحساب بوصفه قيداً خاصاً بالـ endpoint.
        لمستخدمي البوابة يُستخدم sudo لقراءة الفاتورة بعد التحقق من الملكية.
        """
        try:
            order_id = int(order_id)
        except (TypeError, ValueError):
            return request.env['sale.order']
        authorized_accounts = self._get_authorized_accounts()
        # Authorization first: ORM Record Rules enforce org scope for internal users
        # + explicit customer ownership check for both internal and portal principals.
        # Do NOT use sudo().browse() before authorization.
        Order = request.env['sale.order']
        order = Order.search([
            ('id', '=', order_id),
            ('customer_id', 'in', authorized_accounts.ids),
        ], limit=1)
        return order

    def _get_current_collector(self):
        """Return the authenticated field collector, or fail closed.

        The endpoint performs financial writes with a deliberately scoped
        sudo after this check because a field collector is not an Accounting
        user.  The selected staff member and the collector cash journal are
        nevertheless enforced again by ``account.payment`` on creation.
        """
        user = request.env.user
        if not user.has_group('utility_core.group_utility_collector'):
            return False, self._error(
                'COLLECTOR_ROLE_REQUIRED',
                'This operation is restricted to field collectors.',
            )
        collector = request.env['utility.staff'].sudo().search([
            ('user_id', '=', user.id),
            ('company_id', '=', request.env.company.id),
            ('role_ids.code', '=', 'collector'),
        ], limit=1)
        if not collector:
            return False, self._error(
                'COLLECTOR_PROFILE_MISSING',
                'No active field-collector profile is configured for this user.',
            )
        if not collector.collection_journal_id:
            return False, self._error(
                'COLLECTOR_CASH_JOURNAL_MISSING',
                'A dedicated cash journal must be configured for this collector.',
            )
        return collector, False

    @staticmethod
    def _collection_receipt_payload(payment, collection, duplicate=False):
        return {
            'success': True,
            'duplicate': duplicate,
            'payment_id': payment.id,
            'collection_id': collection.id,
            'reference': collection.name or payment.name,
            'payment_reference': payment.name,
            'amount': payment.amount,
            'paid_at': fields.Datetime.to_string(collection.collection_date),
            'state': collection.state,
        }

    def _collector_account_payload(self, customer):
        """Return a live, payable-invoice view for one already-authorized account."""
        orders = request.env['sale.order'].search([
            ('customer_id', '=', customer.id),
            ('state', '!=', 'cancel'),
        ], order='date_order desc, id desc')
        bills = []
        for order in orders:
            # The customer and sale order were resolved with the caller's
            # normal ACL/rules.  Invoice data is read only through this exact,
            # already-authorized bill; no client-supplied invoice is browsed.
            invoices = order.sudo()._get_posted_utility_moves().filtered(
                lambda move: move.move_type == 'out_invoice'
                and move.amount_residual > 0)
            for invoice in invoices:
                due_date = order.date_order.date().isoformat() if order.date_order else None
                bills.append({
                    'order_id': order.id,
                    'invoice_id': invoice.id,
                    'bill_number': order.name,
                    'invoice_number': invoice.name,
                    'amount': invoice.amount_total,
                    'amount_residual': invoice.amount_residual,
                    'due_date': due_date,
                    'state': order.bill_state,
                    'overdue': bool(order.is_overdue),
                })
        total_due = sum(bill['amount_residual'] for bill in bills)
        current_bill = bills[0]['amount_residual'] if bills else 0.0
        debt_amount = max(total_due - current_bill, 0.0)
        meter = customer.meter_id
        return {
            'success': True,
            'account': {
                **self._customer_payload(customer),
                'account_number': customer.account_number or customer.customer_number,
                'meter_number': meter.meter_number if meter else None,
                'meter_id': meter.id if meter else None,
                'connection_status': meter.connection_status if meter else None,
                'accounting_balance': customer.accounting_balance,
                'due_amount': total_due,
                'current_bill': current_bill,
                'debt_amount': debt_amount,
                'allow_partial': True,
                'bills': bills,
            },
        }

    @http.route('/api/v1/utility/collector/account', type='json', auth='user', methods=['POST'])
    def collector_account(self, **kwargs):
        """Look up one account and its actual payable invoice targets."""
        _collector, error = self._get_current_collector()
        if error:
            return error
        customer, error_code = self._resolve_authorized_customer(
            request.jsonrequest or {})
        if error_code == 'CUSTOMER_IDENTIFIER_MISMATCH':
            return self._error(error_code, 'Customer identifiers conflict.')
        if error_code == 'CUSTOMER_IDENTIFIER_REQUIRED':
            return self._error(error_code, 'A customer identifier is required.')
        if not customer:
            return self._error(error_code or 'CUSTOMER_NOT_FOUND', 'Account not found.')
        return self._collector_account_payload(customer)

    @http.route('/api/v1/utility/collector/collect_cash', type='json', auth='user', methods=['POST'])
    def collector_collect_cash(self, **kwargs):
        """Post one idempotent, exact-invoice field cash collection.

        A successful response exists only after Odoo posted the payment,
        reconciled it against the selected invoice, and created the collector
        custody record.  It intentionally does not queue or print an
        unacknowledged financial transaction on the device.
        """
        params = request.jsonrequest or {}
        collector, error = self._get_current_collector()
        if error:
            return error
        request_key = (params.get('idempotency_key') or '').strip()
        if len(request_key) < 8 or len(request_key) > 128:
            return self._error(
                'INVALID_IDEMPOTENCY_KEY',
                'idempotency_key must contain 8 to 128 characters.',
            )
        try:
            order_id = int(params.get('order_id'))
            invoice_id = int(params.get('invoice_id'))
            amount = float(params.get('amount'))
        except (TypeError, ValueError):
            return self._error(
                'VALIDATION_ERROR',
                'order_id, invoice_id and a positive numeric amount are required.',
            )
        if amount <= 0:
            return self._error('VALIDATION_ERROR', 'amount must be positive.')

        order = self._authorize_order(order_id)
        if not order:
            return self._error('ORDER_NOT_FOUND', 'Bill not found in your assigned scope.')
        if order.company_id != collector.company_id:
            return self._error('COMPANY_MISMATCH', 'The bill is not in the collector company.')

        authorized_invoices = order.sudo()._get_posted_utility_moves().filtered(
            lambda move: move.id == invoice_id and move.move_type == 'out_invoice')
        if not authorized_invoices:
            return self._error(
                'INVALID_INVOICE',
                'The selected invoice does not belong to this bill or is not posted.',
            )
        invoice = authorized_invoices[:1]

        Payment = request.env['account.payment'].sudo().with_company(order.company_id)
        existing = Payment.search([
            ('company_id', '=', order.company_id.id),
            ('collection_request_key', '=', request_key),
        ], limit=1)
        if existing:
            if (existing.collector_id != collector
                    or existing.utility_sale_order_id != order
                    or existing.utility_invoice_id != invoice
                    or existing.amount != amount):
                return self._error(
                    'IDEMPOTENCY_KEY_REUSED',
                    'This idempotency key belongs to a different collection request.',
                )
            collection = request.env['utility.collection'].sudo().search(
                [('payment_id', '=', existing.id)], limit=1)
            if not collection or existing.state != 'posted':
                return self._error(
                    'COLLECTION_IN_PROGRESS',
                    'The original collection request is still being processed.',
                )
            return self._collection_receipt_payload(existing, collection, duplicate=True)

        method_line = collector.collection_journal_id.inbound_payment_method_line_ids[:1]
        if not method_line:
            return self._error(
                'COLLECTOR_PAYMENT_METHOD_MISSING',
                'No inbound payment method is configured on the collector cash journal.',
            )
        if amount > invoice.amount_residual:
            return self._error(
                'AMOUNT_EXCEEDS_RESIDUAL',
                'amount cannot exceed the selected invoice residual.',
            )

        try:
            with request.env.cr.savepoint():
                payment = Payment.create({
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'amount': amount,
                    'currency_id': invoice.currency_id.id,
                    'utility_sale_order_id': order.id,
                    'utility_invoice_id': invoice.id,
                    'utility_payment_method': 'cash',
                    'collector_id': collector.id,
                    'payment_method_line_id': method_line.id,
                    'collection_request_key': request_key,
                    'collection_request_user_id': request.env.user.id,
                    'ref': 'MOBILE-COLLECT:%s' % request_key,
                })
        except IntegrityError as exc:
            if getattr(exc, 'pgcode', None) != '23505':
                raise
            payment = Payment.search([
                ('company_id', '=', order.company_id.id),
                ('collection_request_key', '=', request_key),
            ], limit=1)
            if not payment:
                raise
            collection = request.env['utility.collection'].sudo().search(
                [('payment_id', '=', payment.id)], limit=1)
            if payment.state == 'posted' and collection:
                return self._collection_receipt_payload(payment, collection, duplicate=True)
            return self._error('COLLECTION_IN_PROGRESS', 'The original request is still being processed.')

        try:
            payment.action_post()
        except (AccessError, UserError, ValidationError) as exc:
            return self._error('COLLECTION_REJECTED', str(exc))
        collection = request.env['utility.collection'].sudo().search(
            [('payment_id', '=', payment.id)], limit=1)
        if payment.state != 'posted' or not collection or collection.state != 'posted':
            # This indicates an unexpected programming/configuration fault.
            # It must roll back rather than create a receipt for partial work.
            raise ValidationError('Field collection did not reach a posted custody state.')
        return self._collection_receipt_payload(payment, collection)

    @http.route('/api/v1/utility/billing/balance', type='json', auth='user', methods=['POST'])
    def billing_balance(self, **kwargs):
        params = request.jsonrequest
        customer_number = params.get('customer_number')
        if not customer_number:
            return self._error('VALIDATION_ERROR', 'customer_number is required')
        account = self._authorize_account(customer_number)
        if not account:
            return self._error('CUSTOMER_NOT_FOUND', 'Account not found')
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
            return self._error('VALIDATION_ERROR', 'customer_number is required')
        account = self._authorize_account(customer_number)
        if not account:
            return self._error('CUSTOMER_NOT_FOUND', 'Account not found')
        try:
            limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            return self._error('INVALID_LIMIT', 'limit must be numeric')
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
        return self._error(
            'ENDPOINT_DISABLED',
            'Direct payment creation is disabled. Use /api/v1/utility/billing/payment_intent instead.',
        )

    @http.route('/api/v1/utility/billing/payment_intent', type='json', auth='user', methods=['POST'])
    def billing_payment_intent(self, **kwargs):
        params = request.jsonrequest
        order_id = params.get('order_id')
        amount = params.get('amount')
        provider_id = params.get('provider_id')
        invoice_id = params.get('invoice_id')
        direction = params.get('payment_direction', 'inbound')
        if direction != 'inbound':
            return self._error(
                'INVALID_PAYMENT_DIRECTION',
                'Customer payment intents support inbound payments only',
            )

        if not order_id or not amount:
            return self._error('VALIDATION_ERROR', 'order_id and amount are required')
        order = self._authorize_order(order_id)
        if not order:
            return self._error('ORDER_NOT_FOUND', 'Order not found')
        posted_moves = order._get_posted_utility_moves()
        if invoice_id:
            try:
                invoice_id = int(invoice_id)
            except (TypeError, ValueError):
                return self._error('VALIDATION_ERROR', 'invoice_id must be numeric')
            invoice = request.env['account.move'].sudo().browse(invoice_id).exists()
            if (not invoice or len(invoice) != 1 or invoice not in posted_moves
                    or invoice.partner_id != order.partner_id):
                return self._error(
                    'INVALID_INVOICE',
                    'invoice_id must identify a posted accounting invoice of this bill',
                )
        elif len(posted_moves) == 1:
            invoice = posted_moves
        else:
            return self._error(
                'INVOICE_REQUIRED',
                'invoice_id is required when the bill has multiple accounting invoices',
            )
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return self._error('VALIDATION_ERROR', 'amount must be a positive number')
        if amount <= 0:
            return self._error('VALIDATION_ERROR', 'amount must be a positive number')

        if direction == 'inbound':
            if amount > invoice.amount_residual:
                return self._error(
                    'AMOUNT_EXCEEDS_RESIDUAL',
                    'amount cannot exceed the selected invoice residual',
                )
            if order.bill_state in ('paid', 'cancelled'):
                return self._error('BILL_NOT_PAYABLE', 'Bill is not payable')

        Provider = request.env['utility.integration.provider'].sudo()
        if provider_id:
            try:
                provider_id = int(provider_id)
            except (TypeError, ValueError):
                return self._error('VALIDATION_ERROR', 'provider_id must be numeric')
            provider = Provider.browse(provider_id)
        else:
            provider = Provider.search([
                ('is_payment_capable', '=', True),
                ('payment_direction', 'in', (direction, 'both')),
                ('active', '=', True),
                ('company_id', '=', order.company_id.id),
            ], limit=1)

        if not provider or not provider.active or not provider.is_payment_capable:
            return self._error(
                'PAYMENT_PROVIDER_UNAVAILABLE',
                'No active payment provider configured for the requested operation',
            )
        if not provider.supports_direction(direction):
            return self._error(
                'PAYMENT_DIRECTION_UNSUPPORTED',
                'Provider %s does not support payment direction: %s' % (provider.name, direction),
            )
        if provider.company_id and provider.company_id != order.company_id:
            return self._error(
                'PAYMENT_PROVIDER_COMPANY_MISMATCH',
                'Payment provider is not available for the bill company',
            )

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
        # 1. Search transaction by reference WITHOUT locking first
        tx = request.env['utility.payment.gateway.transaction'].sudo().search([
            ('name', '=', reference),
        ], limit=1)
        if not tx:
            return self._error('TRANSACTION_NOT_FOUND', 'Transaction not found')

        # 2. Verify callback token BEFORE acquiring DB row-level lock
        token = params.get('token') or params.get('callback_token') or params.get('signature')
        if not token or not tx.access_token:
            _logger.warning('Payment webhook missing token for reference %s', reference)
            return self._error('AUTHENTICATION_REQUIRED', 'Missing authentication token')
        expected = tx.access_token.encode('utf-8')
        received = token.encode('utf-8')
        if len(expected) != len(received) or not hmac.compare_digest(expected, received):
            _logger.warning('Payment webhook invalid token for reference %s', reference)
            return self._error('INVALID_TOKEN', 'Invalid token')

        # 3. Acquire FOR UPDATE row-level lock ONLY AFTER authentication succeeds
        request.env.cr.execute(
            "SELECT id FROM utility_payment_gateway_transaction WHERE name = %s FOR UPDATE",
            [reference]
        )
        tx.invalidate_recordset(['state', 'payment_id', 'callback_payload', 'error_message'])

        status = params.get('status')
        if not status:
            return self._error('VALIDATION_ERROR', 'Payment status is required')
        provider_reference = params.get('provider_reference') or params.get('reference')
        if tx.state == 'done':
            return {'success': True, 'state': tx.state, 'payment_id': tx.payment_id.id if tx.payment_id else False}
        if tx.state != 'pending':
            return self._error(
                'INVALID_TRANSACTION_STATE',
                'Only pending payment transactions can receive callbacks',
            )
        if status in ('success', 'done', 'paid') and not provider_reference:
            return self._error(
                'VALIDATION_ERROR',
                'Provider reference is required for successful payments',
            )
        sanitized_params = str(sanitize_sensitive_payload(params))
        if status not in ('success', 'done', 'paid'):
            tx.write({
                'state': 'failed',
                'callback_payload': sanitized_params,
                'error_message': params.get('error') or 'Payment gateway reported failure',
            })
            error_response = self._error(
                'PAYMENT_FAILED',
                params.get('error') or 'Payment gateway reported failure',
            )
            error_response['state'] = tx.state
            return error_response
        tx.action_confirm_payment(provider_reference=provider_reference, callback_payload=sanitized_params)
        return {'success': True, 'state': tx.state, 'payment_id': tx.payment_id.id if tx.payment_id else False}

    @http.route('/api/v1/utility/operations/service_request', type='json', auth='user', methods=['POST'])
    def service_request(self, **kwargs):
        """إنشاء طلب خدمة.  التفويض يسبق أي وصول للسجل:
        - نحدد أولاً الحسابات المصرح بها لهذا المستخدم (ORM Record Rules + ملكية حساب).
        - نبحث ضمن تلك الحسابات فقط — لا sudo().browse() قبل التفويض.
        - بعد التحقق من الهوية والملكية، يُنشأ أمر الخدمة.
        """
        params = request.jsonrequest
        customer_id = params.get('customer_id')
        service_type = params.get('service_type')
        description = params.get('description')
        if not customer_id or not service_type or not description:
            return self._error(
                'VALIDATION_ERROR',
                'customer_id, service_type, and description are required',
            )
        try:
            customer_id = int(customer_id)
        except (TypeError, ValueError):
            return self._error('VALIDATION_ERROR', 'customer_id must be numeric')
        # Authorization FIRST: search within authorized scope, no sudo() before auth.
        authorized = self._get_authorized_accounts()
        account = authorized.filtered(lambda c: c.id == customer_id)[:1]
        if not account:
            return self._error('CUSTOMER_NOT_FOUND', 'Customer account not found')
        try:
            order = request.env['utility.service.order'].sudo().create({
                'customer_id': account.id,
                'service_type': service_type,
                'description': description,
                'state': 'draft',
            })
            return {'order_number': order.order_number}
        except KeyError:
            return self._error('MODEL_UNAVAILABLE', 'utility.service.order model not available')

    @http.route('/api/v1/utility/reports/daily', type='json', auth='user', methods=['POST'])
    def reports_daily(self, **kwargs):
        from datetime import date
        params = request.jsonrequest
        report_date = params.get('date', date.today().isoformat())
        region_id = params.get('region_id')
        area_id = params.get('area_id')
        user = request.env.user
        if not user.has_group('base.group_user'):
            return self._error(
                'ACCESS_DENIED',
                'Access denied. Reports are for internal users only.',
            )
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
            try:
                bills_domain.append(('customer_id.region_id', '=', int(region_id)))
            except (TypeError, ValueError):
                return self._error('VALIDATION_ERROR', 'region_id must be numeric')
        if area_id:
            try:
                bills_domain.append(('customer_id.area_id', '=', int(area_id)))
            except (TypeError, ValueError):
                return self._error('VALIDATION_ERROR', 'area_id must be numeric')
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
            ('state', 'not in', ('resolved', 'dismissed')),
        ]
        active_alarms = request.env['utility.alarm'].search_count(alarms_domain)

        return {
            'total_bills': total_bills,
            'total_collections': total_collections,
            'active_alarms': active_alarms,
        }
