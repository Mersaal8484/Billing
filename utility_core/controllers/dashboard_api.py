import json
from odoo import http, fields
from odoo.http import request
from datetime import datetime, timedelta
import pytz

class UtilityDashboardAPI(http.Controller):

    @http.route('/utility/dashboard/kpi', type='json', auth='user')
    def get_kpis(self):
        # 1. Today's Collections (Prepaid POS + Postpaid Payments)
        today = fields_date.context_today(request.env.user) if hasattr(request.env['res.users'], 'context_today') else datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # POS Sales (Prepaid)
        prepaid_total = 0.0
        pos_orders = request.env.get('pos.order')
        if pos_orders is not None:
            pos_orders_today = pos_orders.sudo().search([
                ('date_order', '>=', today_start),
                ('date_order', '<=', today_end),
                ('state', 'in', ['paid', 'done', 'invoiced'])
            ])
            prepaid_total = sum(pos_orders_today.mapped('amount_paid'))

        # Postpaid Payments
        postpaid_total = 0.0
        account_payment = request.env.get('account.payment')
        if account_payment is not None:
            payments = account_payment.sudo().search([
                ('date', '=', today),
                ('state', '=', 'posted'),
                ('payment_type', '=', 'inbound')
            ])
            postpaid_total = sum(payments.mapped('amount'))

        # 2. Open Postpaid Debt
        total_debt = 0.0
        account_move = request.env.get('account.move')
        if account_move is not None:
            open_invoices = account_move.sudo().search([
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial'])
            ])
            total_debt = sum(open_invoices.mapped('amount_residual'))

        # 3. Active Customers Statistics
        customers = request.env['utility.customer'].sudo().read_group(
            domain=[('state', '=', 'active')],
            fields=['category_id'],
            groupby=['category_id']
        )
        total_customers = sum(c['category_id_count'] for c in customers)

        # 4. Invoices and Collections (Last 7 days)
        labels = []
        invoices_data = []
        collections_data = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            labels.append(d.strftime('%Y-%m-%d'))
            
            # invoices issued that day
            day_invs_total = 0.0
            if account_move is not None:
                day_invs = account_move.sudo().search([
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                    ('invoice_date', '=', d)
                ])
                day_invs_total = sum(day_invs.mapped('amount_total'))
            invoices_data.append(day_invs_total)
            
            # collections that day
            day_pays_total = 0.0
            if account_payment is not None:
                day_pays = account_payment.sudo().search([
                    ('state', '=', 'posted'),
                    ('payment_type', '=', 'inbound'),
                    ('date', '=', d)
                ])
                day_pays_total = sum(day_pays.mapped('amount'))
            collections_data.append(day_pays_total)

        return {
            'today_prepaid': prepaid_total,
            'today_postpaid': postpaid_total,
            'total_debt': total_debt,
            'active_customers': total_customers,
            'chart_labels': labels,
            'chart_invoices': invoices_data,
            'chart_collections': collections_data,
        }
