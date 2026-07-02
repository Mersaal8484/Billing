from odoo import fields, http
from odoo.http import request
from datetime import datetime, date


class UtilityAPI(http.Controller):

    @http.route('/api/v1/utility/billing/balance', type='json', auth='user', methods=['POST'])
    def billing_balance(self, **kwargs):
        params = request.jsonrequest
        account_number = params.get('account_number')
        if not account_number:
            return {'error': 'account_number is required'}
        account = request.env['utility.customer'].search([('account_number', '=', account_number)], limit=1)
        if not account:
            return {'error': 'Account not found'}
        orders = request.env['sale.order'].search([
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
        account = request.env['utility.customer'].search([('account_number', '=', account_number)], limit=1)
        if not account:
            return {'error': 'Account not found'}
        orders = request.env['sale.order'].search([
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
        order = request.env['sale.order'].browse(int(order_id))
        if not order.exists():
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
        payment = request.env['account.payment'].create({
            'partner_id': partner.id if partner else request.env.user.partner_id.id,
            'amount': amount,
            'payment_type': 'inbound',
            'partner_type': 'customer',
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
        pos_domain = [('date_order', '>=', '%s 00:00:00' % report_date), ('date_order', '<=', '%s 23:59:59' % report_date)]
        if region_id:
            pos_domain.append(('account_id.region_id', '=', int(region_id)))
        if area_id:
            pos_domain.append(('account_id.area_id', '=', int(area_id)))
        pos_orders = request.env['pos.order'].search(pos_domain)
        bills_domain = [('date_order', '>=', '%s 00:00:00' % report_date), ('date_order', '<=', '%s 23:59:59' % report_date)]
        if region_id:
            bills_domain.append(('customer_id.region_id', '=', int(region_id)))
        if area_id:
            bills_domain.append(('customer_id.area_id', '=', int(area_id)))
        orders = request.env['sale.order'].search(bills_domain)
        alarms_domain = [('alarm_date', '>=', '%s 00:00:00' % report_date), ('alarm_date', '<=', '%s 23:59:59' % report_date), ('state', 'not in', ('resolved', 'closed'))]
        alarms = request.env['utility.alarm'].search(alarms_domain)
        total_collections = sum(request.env['account.payment'].search([
            ('date', '=', report_date),
            ('utility_sale_order_id', '!=', False),
        ]).mapped('amount'))
        return {
            'total_pos_sales': len(pos_orders),
            'total_pos_revenue': sum(pos_orders.mapped('amount_paid')),
            'total_bills': len(orders),
            'total_collections': total_collections,
            'active_alarms': len(alarms),
        }
