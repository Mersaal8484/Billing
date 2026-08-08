from odoo import fields, http
from odoo.http import request
from datetime import datetime, date


class UtilityAPI(http.Controller):

    def _get_authorized_accounts(self):
        """إرجاع recordset لحسابات الكهرباء المسموح للمستخدم الحالي الوصول إليها.

        للمستخدمين الداخليين: كل الحسابات.
        لمستخدمي البوابة: الحسابات المرتبطة بـ partner الخاص بهم فقط.
        """
        user = request.env.user
        if user.has_group('base.group_user'):
            return request.env['utility.customer'].sudo().search([])
        return request.env['utility.customer'].sudo().search([
            ('partner_id', '=', user.partner_id.id),
        ])

    def _authorize_account(self, account_number):
        """التحقق من ملكية حساب الكهرباء وإرجاعه إن وجد."""
        accounts = self._get_authorized_accounts()
        return accounts.filtered(lambda a: a.account_number == account_number)[:1]

    def _authorize_order(self, order_id):
        """التحقق من ملكية الفاتورة وإرجاعها إن وجدت."""
        user = request.env.user
        order = request.env['sale.order'].sudo().browse(int(order_id))
        if not order.exists():
            return request.env['sale.order']
        if user.has_group('base.group_user'):
            return order
        if order.customer_id and order.customer_id.partner_id.id == user.partner_id.id:
            return order
        return request.env['sale.order']

    @http.route('/api/v1/utility/billing/balance', type='json', auth='user', methods=['POST'])
    def billing_balance(self, **kwargs):
        params = request.jsonrequest
        account_number = params.get('account_number')
        if not account_number:
            return {'error': 'account_number is required'}
        account = self._authorize_account(account_number)
        if not account:
            return {'error': 'Account not found'}
        orders = request.env['sale.order'].sudo().search([
            ('customer_id', '=', account.id),
            ('bill_state', 'not in', ('paid', 'cancelled')),
        ])
        debt = sum(orders.mapped('balance_due'))
        return {
            'account_number': account.account_number,
            'balance': account.balance,
            'emergency_credit': account.emergency_credit,
            'debt': debt,
            'last_purchase_date': account.last_purchase_date.isoformat() if account.last_purchase_date else None,
        }

    @http.route('/api/v1/utility/billing/bills', type='json', auth='user', methods=['POST'])
    def billing_bills(self, **kwargs):
        params = request.jsonrequest
        account_number = params.get('account_number')
        limit = params.get('limit', 12)
        if not account_number:
            return {'error': 'account_number is required'}
        account = self._authorize_account(account_number)
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
        params = request.jsonrequest
        order_id = params.get('order_id')
        amount = params.get('amount')
        payment_method = params.get('payment_method', 'cash')
        reference = params.get('reference', '')
        if not order_id or not amount:
            return {'error': 'order_id and amount are required'}
        order = self._authorize_order(order_id)
        if not order:
            return {'error': 'Order not found'}
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return {'error': 'amount must be a positive number'}
        if amount <= 0:
            return {'error': 'amount must be a positive number'}
        if order.bill_state in ('paid', 'cancelled'):
            return {'error': 'Bill is not payable'}
        partner = order.partner_id
        journal_id = params.get('journal_id', 0) or int(
            request.env['ir.config_parameter'].sudo().get_param('utility.collection_journal_id', 0))
        journal = request.env['account.journal'].sudo().browse(journal_id) if journal_id else False
        if not journal or not journal.inbound_payment_method_line_ids:
            journal = request.env['account.journal'].sudo().search([
                ('type', '=', 'bank'), ('company_id', '=', request.env.company.id),
            ], limit=1)
        if not journal or not journal.inbound_payment_method_line_ids:
            return {'error': 'لم يتم العثور على يومية دفع واردة. يرجى ضبط الإعدادات.'}
        payment_method_line = journal.inbound_payment_method_line_ids[:1]
        payment = request.env['account.payment'].sudo().create({
            'partner_id': partner.id if partner else request.env.user.partner_id.id,
            'amount': amount,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'journal_id': journal.id,
            'payment_method_line_id': payment_method_line.id,
            'utility_sale_order_id': order.id,
            'utility_payment_method': payment_method,
            'electronic_doc_no': reference,
            'date': fields.Date.context_today(request.env.user),
        })
        payment.action_post()
        return {
            'payment_id': payment.id,
            'state': payment.state,
            'success': True,
        }

    @http.route('/api/v1/utility/billing/payment_intent', type='json', auth='user', methods=['POST'])
    def billing_payment_intent(self, **kwargs):
        params = request.jsonrequest
        order_id = params.get('order_id')
        amount = params.get('amount')
        provider_id = params.get('provider_id')
        if not order_id or not amount:
            return {'error': 'order_id and amount are required'}
        order = self._authorize_order(order_id)
        if not order:
            return {'error': 'Order not found'}
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return {'error': 'amount must be a positive number'}
        if amount <= 0:
            return {'error': 'amount must be a positive number'}
        if order.bill_state in ('paid', 'cancelled'):
            return {'error': 'Bill is not payable'}
        Provider = request.env['utility.integration.provider'].sudo()
        provider = Provider.browse(int(provider_id)) if provider_id else Provider.search([
            ('provider_type', '=', 'payment_gateway'), ('active', '=', True)
        ], limit=1)
        if not provider or provider.provider_type != 'payment_gateway':
            return {'error': 'No active payment gateway provider configured'}
        tx = request.env['utility.payment.gateway.transaction'].sudo().create({
            'provider_id': provider.id,
            'sale_order_id': order.id,
            'amount': amount,
        })
        tx.action_mark_pending()
        return {
            'transaction_id': tx.id,
            'reference': tx.name,
            'state': tx.state,
            'amount': tx.amount,
            'callback_token': tx.access_token,
        }

    @http.route('/api/v1/utility/payment_gateway/webhook/<string:reference>', type='json', auth='public', methods=['POST'], csrf=False)
    def payment_gateway_webhook(self, reference, **kwargs):
        params = request.jsonrequest or {}
        tx = request.env['utility.payment.gateway.transaction'].sudo().search([
            ('name', '=', reference),
        ], limit=1)
        if not tx:
            return {'error': 'Transaction not found'}
        token = params.get('token') or params.get('callback_token')
        if token != tx.access_token:
            return {'error': 'Invalid token'}
        status = params.get('status', 'success')
        provider_reference = params.get('provider_reference') or params.get('reference')
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
        account = request.env['utility.customer'].sudo().browse(int(customer_id))
        if not account.exists():
            return {'error': 'Customer account not found'}
        user = request.env.user
        if not user.has_group('base.group_user') and account.partner_id.id != user.partner_id.id:
            return {'error': 'Customer account not found'}
        try:
            order = request.env['utility.service.order'].sudo().create({
                'customer_id': int(customer_id),
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
        try:
            reading_value = float(reading_value)
        except (TypeError, ValueError):
            return {'error': 'reading_value must be numeric'}
        date_range_id = params.get('date_range_id') or False
        reading = meter.create_ami_reading(
            reading_value,
            reading_date=params.get('reading_date') or False,
            date_range_id=int(date_range_id) if date_range_id else False,
        )
        provider.call_json({
            'meter_number': meter_number,
            'reading_id': reading.reading_id,
            'reading_value': reading_value,
        }, 'ami.reading.callback', record=reading)
        return {'success': True, 'reading_id': reading.id, 'reading_number': reading.reading_id}
    @http.route('/api/v1/utility/reports/daily', type='json', auth='user', methods=['POST'])
    def reports_daily(self, **kwargs):
        from datetime import date, datetime as dt
        params = request.jsonrequest
        report_date = params.get('date', date.today().isoformat())
        region_id = params.get('region_id')
        area_id = params.get('area_id')
        user = request.env.user
        if not user.has_group('base.group_user'):
            return {'error': 'Access denied. Reports are for internal users only.'}
        start_dt = '%s 00:00:00' % report_date
        end_dt = '%s 23:59:59' % report_date

        pos_domain = [('date_order', '>=', start_dt), ('date_order', '<=', end_dt)]
        if region_id:
            pos_domain.append(('account_id.region_id', '=', int(region_id)))
        if area_id:
            pos_domain.append(('account_id.area_id', '=', int(area_id)))
        total_pos_sales = request.env['pos.order'].sudo().search_count(pos_domain)
        pos_rev_data = request.env['pos.order'].sudo().read_group(
            pos_domain, ['amount_paid:sum'], [])
        total_pos_revenue = pos_rev_data[0]['amount_paid'] if pos_rev_data else 0.0

        bills_domain = [('date_order', '>=', start_dt), ('date_order', '<=', end_dt)]
        if region_id:
            bills_domain.append(('customer_id.region_id', '=', int(region_id)))
        if area_id:
            bills_domain.append(('customer_id.area_id', '=', int(area_id)))
        total_bills = request.env['sale.order'].sudo().search_count(bills_domain)

        payments_domain = [('date', '=', report_date), ('utility_sale_order_id', '!=', False)]
        pay_data = request.env['account.payment'].sudo().read_group(
            payments_domain, ['amount:sum'], [])
        total_collections = pay_data[0].get('amount', 0) if pay_data else 0.0

        alarms_domain = [
            ('alarm_date', '>=', start_dt), ('alarm_date', '<=', end_dt),
            ('state', 'not in', ('resolved', 'closed')),
        ]
        active_alarms = request.env['utility.alarm'].sudo().search_count(alarms_domain)

        return {
            'total_pos_sales': total_pos_sales,
            'total_pos_revenue': total_pos_revenue,
            'total_bills': total_bills,
            'total_collections': total_collections,
            'active_alarms': active_alarms,
        }
