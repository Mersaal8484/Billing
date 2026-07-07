from odoo import http
from odoo.http import request


class UtilityAPI(http.Controller):

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
            return {'error': 'Provide at least one search criterion'}
        customers = request.env['utility.customer'].search(domain, limit=10)
        return {
            'count': len(customers),
            'customers': [{
                'id': c.id,
                'customer_number': c.customer_number,
                'name': c.partner_id.name,
                'national_id': c.national_id,
                'mobile': c.mobile,
                'customer_type': c.customer_type,
                'connection_status': c.connection_status,
                'region': c.region_id.name if c.region_id else None,
                'area': c.area_id.name if c.area_id else None,
            } for c in customers],
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
            return {'error': 'Provide meter number or serial number'}
        meters = request.env['utility.meter'].search(domain, limit=10)
        return {
            'count': len(meters),
            'meters': [{
                'id': m.id,
                'meter_number': m.meter_number,
                'serial_number': m.serial_number,
                'status': m.status_id.name if m.status_id else None,
                'type': m.meter_type_id.name if m.meter_type_id else None,
                'phase': m.phase,
                'customer': m.customer_id.partner_id.name if m.customer_id else None,
                'account': m.account_id.account_number if m.account_id else None,
                'region': m.region_id.name if m.region_id else None,
                'area': m.area_id.name if m.area_id else None,
            } for m in meters],
        }

    @http.route('/api/v1/utility/sale', type='json', auth='user', methods=['POST'])
    def process_sale(self, **kwargs):
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
            'customer_id': account.customer_id.id,
            'account_id': account.id,
            'meter_id': meter.id,
            'tariff_id': account.tariff_id.id,
            'amount_paid': amount,
            'payment_method': payment_method,
            'operator_id': request.env.user.id,
        })
        sale.action_calculate()
        sale.action_confirm()
        sale.action_generate_token()
        sale.action_complete()
        return {
            'success': True,
            'receipt_number': sale.receipt_number,
            'kwh': sale.kwh_purchased,
            'token': sale.token_id.token_number if sale.token_id else None,
            'balance_after': sale.balance_after,
        }

    @http.route('/api/v1/utility/token/validate', type='json', auth='user', methods=['POST'])
    def validate_token(self, **kwargs):
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
        if token:
            return {
                'valid': True,
                'amount': token.amount,
                'kwh': token.kwh,
                'date': token.request_date.isoformat() if token.request_date else None,
            }
        return {'valid': False}

    @http.route('/api/v1/utility/payment', type='json', auth='user', methods=['POST'])
    def register_payment(self, **kwargs):
        params = request.jsonrequest
        account_number = params.get('account_number')
        amount = params.get('amount')
        payment_method = params.get('payment_method', 'cash')
        if not account_number or not amount:
            return {'error': 'account_number and amount are required'}
        account = request.env['utility.account'].search([('account_number', '=', account_number)], limit=1)
        if not account:
            return {'error': 'Account not found'}
        payment = request.env['utility.payment'].create({
            'customer_id': account.customer_id.id,
            'account_id': account.id,
            'amount': amount,
            'payment_method': payment_method,
            'operator_id': request.env.user.id,
        })
        payment.action_confirm()
        return {
            'success': True,
            'payment_reference': payment.payment_reference,
        }

    @http.route('/api/v1/utility/reversal', type='json', auth='user', methods=['POST'])
    def create_reversal(self, **kwargs):
        params = request.jsonrequest
        receipt_number = params.get('receipt_number')
        reason = params.get('reason', '')
        if not receipt_number:
            return {'error': 'receipt_number is required'}
        sale = request.env['utility.sale'].search([('receipt_number', '=', receipt_number)], limit=1)
        if not sale:
            return {'error': 'Sale not found'}
        reversal = request.env['utility.reversal'].create({
            'customer_id': sale.customer_id.id,
            'account_id': sale.account_id.id,
            'meter_id': sale.meter_id.id,
            'sale_id': sale.id,
            'amount': sale.amount_paid,
            'reason': reason or 'API reversal',
        })
        reversal.action_approve()
        reversal.action_complete()
        return {
            'success': True,
            'reversal_reference': reversal.reference,
        }

    @http.route('/api/v1/utility/reports/daily_sales', type='json', auth='user', methods=['POST'])
    def daily_sales_report(self, **kwargs):
        params = request.jsonrequest
        date = params.get('date')
        region_id = params.get('region_id')
        area_id = params.get('area_id')
        domain = [('state', '=', 'completed')]
        if date:
            domain.append(('date', '>=', f'{date} 00:00:00'))
            domain.append(('date', '<=', f'{date} 23:59:59'))
        if region_id:
            domain.append(('region_id', '=', region_id))
        if area_id:
            domain.append(('area_id', '=', area_id))
        sales = request.env['utility.sale'].search(domain)
        return {
            'total_sales': len(sales),
            'total_revenue': sum(sales.mapped('amount_paid')),
            'total_kwh': sum(sales.mapped('kwh_purchased')),
        }
