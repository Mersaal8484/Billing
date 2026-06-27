from odoo import http
from odoo.http import request


class UtilityPortalAPI(http.Controller):

    @http.route('/api/v1/utility/customer/lookup', type='json', auth='user', methods=['POST'])
    def customer_lookup(self, **kwargs):
        params = request.jsonrequest
        domain = []
        if params.get('customer_number'):
            domain.append(('customer_number', '=', params['customer_number']))
        if params.get('national_id'):
            domain.append(('national_id', '=', params['national_id']))
        if params.get('mobile'):
            domain.append(('mobile', '=', params['mobile']))
        if not domain:
            return {'error': 'Provide customer_number, national_id, or mobile'}
        customer = request.env['utility.customer'].search(domain, limit=1)
        if not customer:
            return {'error': 'Customer not found'}
        partner_customers = request.env['utility.customer'].search([('partner_id', '=', customer.partner_id.id)])
        return {
            'id': customer.id,
            'customer_number': customer.customer_number,
            'name': customer.partner_id.name,
            'national_id': customer.national_id,
            'mobile': customer.mobile,
            'email': customer.partner_id.email,
            'customer_type': customer.subscriber_category_id.name if customer.subscriber_category_id else None,
            'connection_status': customer.connection_status,
            'region': customer.region_id.name if customer.region_id else None,
            'area': customer.area_id.name if customer.area_id else None,
            'accounts': [{
                'id': a.id,
                'account_number': a.account_number,
                'balance': a.balance,
                'state': a.state,
            } for a in partner_customers],
        }

    @http.route('/api/v1/utility/meter/lookup', type='json', auth='user', methods=['POST'])
    def meter_lookup(self, **kwargs):
        params = request.jsonrequest
        domain = []
        if params.get('meter_number'):
            domain.append(('meter_number', '=', params['meter_number']))
        if params.get('serial_number'):
            domain.append(('serial_number', '=', params['serial_number']))
        if not domain:
            return {'error': 'Provide meter_number or serial_number'}
        meter = request.env['utility.meter'].search(domain, limit=1)
        if not meter:
            return {'error': 'Meter not found'}
        return {
            'id': meter.id,
            'meter_number': meter.meter_number,
            'serial_number': meter.serial_number,
            'status': meter.status_id.name if meter.status_id else None,
            'type': meter.meter_type_id.name if meter.meter_type_id else None,
            'phase': meter.phase,
            'customer': meter.customer_id.partner_id.name if meter.customer_id else None,
            'account': meter.account_id.account_number if meter.account_id else None,
            'region': meter.region_id.name if meter.region_id else None,
            'area': meter.area_id.name if meter.area_id else None,
            'route': meter.route_id.name if meter.route_id else None,
            'feeder': meter.feeder_id.name if meter.feeder_id else None,
            'transformer': meter.transformer_id.name if meter.transformer_id else None,
        }

    @http.route('/api/v1/utility/prepaid/sale', type='json', auth='user', methods=['POST'])
    def prepaid_sale(self, **kwargs):
        params = request.jsonrequest
        meter_no = params.get('meter_number')
        amount = params.get('amount')
        payment_method = params.get('payment_method', 'cash')
        if not meter_no or not amount:
            return {'error': 'meter_number and amount are required'}
        meter = request.env['utility.meter'].search([('meter_number', '=', meter_no)], limit=1)
        if not meter:
            return {'error': 'Meter not found'}
        if not meter.account_id:
            return {'error': 'Meter has no active account'}
        account = meter.account_id
        sale = request.env['utility.sale'].create({
            'customer_id': account.partner_id.id,
            'account_id': account.id,
            'meter_id': meter.id,
            'tariff_id': account.tariff_id.id if account.tariff_id else False,
            'amount_paid': amount,
            'payment_method': payment_method,
            'operator_id': request.env.user.id,
        })
        sale.action_confirm()
        sale.action_generate_token()
        sale.action_complete()
        return {
            'receipt_number': sale.receipt_number,
            'amount': sale.amount_paid,
            'kwh': sale.kwh_purchased,
            'token': sale.token_id.token_number if sale.token_id else None,
            'balance_after': sale.balance_after,
        }

    @http.route('/api/v1/utility/prepaid/token/validate', type='json', auth='user', methods=['POST'])
    def token_validate(self, **kwargs):
        params = request.jsonrequest
        token_number = params.get('token_number')
        meter_number = params.get('meter_number')
        if not token_number or not meter_number:
            return {'error': 'token_number and meter_number are required'}
        token = request.env['utility.token'].search([
            ('token_number', '=', token_number),
            ('meter_id.meter_number', '=', meter_number),
            ('status', '=', 'success'),
        ], limit=1)
        if not token:
            return {'valid': False}
        return {
            'valid': True,
            'amount': token.amount,
            'kwh': token.kwh,
            'date': token.request_date.isoformat() if token.request_date else None,
        }

    @http.route('/api/v1/utility/billing/balance', type='json', auth='user', methods=['POST'])
    def billing_balance(self, **kwargs):
        params = request.jsonrequest
        account_number = params.get('account_number')
        if not account_number:
            return {'error': 'account_number is required'}
        account = request.env['utility.customer'].search([('account_number', '=', account_number)], limit=1)
        if not account:
            return {'error': 'Account not found'}
        bills = request.env['utility.bill'].search([
            ('account_id', '=', account.id),
            ('state', 'not in', ('paid', 'cancelled')),
        ])
        debt = sum(bills.mapped('balance_due'))
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
        account = request.env['utility.customer'].search([('account_number', '=', account_number)], limit=1)
        if not account:
            return {'error': 'Account not found'}
        bills = request.env['utility.bill'].search([
            ('account_id', '=', account.id),
        ], order='bill_date desc', limit=limit)
        return {
            'bills': [{
                'bill_number': b.bill_number,
                'period': '%s - %s' % (b.period_start, b.period_end) if b.period_start and b.period_end else None,
                'amount': b.amount_total,
                'paid': b.amount_paid,
                'balance': b.balance_due,
                'due_date': b.due_date.isoformat() if b.due_date else None,
                'state': b.state,
            } for b in bills],
        }

    @http.route('/api/v1/utility/billing/pay', type='json', auth='user', methods=['POST'])
    def billing_pay(self, **kwargs):
        params = request.jsonrequest
        bill_id = params.get('bill_id')
        amount = params.get('amount')
        payment_method = params.get('payment_method', 'cash')
        reference = params.get('reference', '')
        if not bill_id or not amount:
            return {'error': 'bill_id and amount are required'}
        bill = request.env['utility.bill'].browse(int(bill_id))
        if not bill.exists():
            return {'error': 'Bill not found'}
        collection = request.env['utility.collection'].create({
            'customer_id': bill.customer_id.id,
            'account_id': bill.account_id.id,
            'bill_id': bill.id,
            'amount': amount,
            'payment_method': payment_method,
            'reference_number': reference,
            'collected_by': request.env.user.id,
        })
        collection.state = 'collected'
        return {
            'collection_number': collection.collection_number,
            'success': True,
        }

    @http.route('/api/v1/utility/operations/service_request', type='json', auth='user', methods=['POST'])
    def service_request(self, **kwargs):
        params = request.jsonrequest
        customer_id = params.get('customer_id')
        service_type = params.get('service_type')
        description = params.get('description')
        if not customer_id or not service_type or not description:
            return {'error': 'customer_id, service_type, and description are required'}
        try:
            order = request.env['utility.service.order'].create({
                'customer_id': int(customer_id),
                'service_type': service_type,
                'description': description,
                'state': 'draft',
            })
            return {'order_number': order.order_number}
        except KeyError:
            return {'error': 'utility.service.order model not available'}

    @http.route('/api/v1/utility/reports/daily', type='json', auth='user', methods=['POST'])
    def reports_daily(self, **kwargs):
        from datetime import date
        params = request.jsonrequest
        report_date = params.get('date', date.today().isoformat())
        region_id = params.get('region_id')
        area_id = params.get('area_id')
        sales_domain = [('state', '=', 'completed'), ('date', '>=', '%s 00:00:00' % report_date), ('date', '<=', '%s 23:59:59' % report_date)]
        if region_id:
            sales_domain.append(('account_id.region_id', '=', int(region_id)))
        if area_id:
            sales_domain.append(('account_id.area_id', '=', int(area_id)))
        sales = request.env['utility.sale'].search(sales_domain)
        bills_domain = [('bill_date', '=', report_date)]
        if region_id:
            bills_domain.append(('account_id.region_id', '=', int(region_id)))
        if area_id:
            bills_domain.append(('account_id.area_id', '=', int(area_id)))
        bills = request.env['utility.bill'].search(bills_domain)
        collections_domain = [('payment_date', '>=', '%s 00:00:00' % report_date), ('payment_date', '<=', '%s 23:59:59' % report_date)]
        if region_id:
            collections_domain.append(('account_id.region_id', '=', int(region_id)))
        if area_id:
            collections_domain.append(('account_id.area_id', '=', int(area_id)))
        collections = request.env['utility.collection'].search(collections_domain)
        alarms_domain = [('alarm_date', '>=', '%s 00:00:00' % report_date), ('alarm_date', '<=', '%s 23:59:59' % report_date), ('state', 'not in', ('resolved', 'closed'))]
        alarms = request.env['utility.alarm'].search(alarms_domain)
        return {
            'total_sales': len(sales),
            'total_revenue': sum(sales.mapped('amount_paid')),
            'total_kwh': sum(sales.mapped('kwh_purchased')),
            'total_bills': len(bills),
            'total_collections': sum(collections.mapped('amount')),
            'active_alarms': len(alarms),
        }
