from odoo import http, fields
from odoo.http import request
from datetime import datetime, timedelta

class UtilityDashboardAPI(http.Controller):

    @http.route('/utility/dashboard/kpi', type='json', auth='user')
    def get_kpis(self, region_id=False):
        # 1. Today's Collections (Prepaid POS + Postpaid Payments)
        today = fields.Date.context_today(request.env.user)
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        customer_domain = [('state', '=', 'active')]
        if region_id:
            customer_domain.append(('region_id', '=', region_id))
        
        # POS Sales (Prepaid)
        prepaid_total = 0.0
        pos_orders = request.env.get('pos.order')
        if pos_orders is not None:
            pos_domain = [
                ('date_order', '>=', today_start),
                ('date_order', '<=', today_end),
                ('state', 'in', ['paid', 'done', 'invoiced'])
            ]
            if region_id:
                customers = request.env['utility.customer'].sudo().search(customer_domain)
                pos_domain.append(('utility_account_id', 'in', customers.ids))
            pos_orders_today = pos_orders.sudo().search(pos_domain)
            prepaid_total = sum(pos_orders_today.mapped('amount_paid'))

        # Postpaid Payments
        postpaid_total = 0.0
        account_payment = request.env.get('account.payment')
        if account_payment is not None:
            pay_domain = [
                ('date', '=', today),
                ('state', '=', 'posted'),
                ('payment_type', '=', 'inbound')
            ]
            if region_id:
                customers = request.env['utility.customer'].sudo().search(customer_domain)
                partner_ids = customers.mapped('partner_id').ids
                if partner_ids:
                    pay_domain.append(('partner_id', 'in', partner_ids))
            payments = account_payment.sudo().search(pay_domain)
            postpaid_total = sum(payments.mapped('amount'))

        # 2. Open Postpaid Debt
        total_debt = 0.0
        account_move = request.env.get('account.move')
        if account_move is not None:
            inv_domain = [
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial'])
            ]
            if region_id:
                customers = request.env['utility.customer'].sudo().search(customer_domain)
                partner_ids = customers.mapped('partner_id').ids
                if partner_ids:
                    inv_domain.append(('partner_id', 'in', partner_ids))
            open_invoices = account_move.sudo().search(inv_domain)
            total_debt = sum(open_invoices.mapped('amount_residual'))

        # 3. Active Customers Statistics
        customers = request.env['utility.customer'].sudo().read_group(
            domain=customer_domain,
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
                day_inv_domain = [
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                    ('invoice_date', '=', d)
                ]
                if region_id:
                    customers = request.env['utility.customer'].sudo().search(customer_domain)
                    partner_ids = customers.mapped('partner_id').ids
                    if partner_ids:
                        day_inv_domain.append(('partner_id', 'in', partner_ids))
                day_invs = account_move.sudo().search(day_inv_domain)
                day_invs_total = sum(day_invs.mapped('amount_total'))
            invoices_data.append(day_invs_total)
            
            # collections that day
            day_pays_total = 0.0
            if account_payment is not None:
                day_pay_domain = [
                    ('state', '=', 'posted'),
                    ('payment_type', '=', 'inbound'),
                    ('date', '=', d)
                ]
                if region_id:
                    customers = request.env['utility.customer'].sudo().search(customer_domain)
                    partner_ids = customers.mapped('partner_id').ids
                    if partner_ids:
                        day_pay_domain.append(('partner_id', 'in', partner_ids))
                day_pays = account_payment.sudo().search(day_pay_domain)
                day_pays_total = sum(day_pays.mapped('amount'))
            collections_data.append(day_pays_total)

        # 5. Region-level dashboard rows
        region_rows = []
        Customer = request.env['utility.customer'].sudo()
        
        if region_id:
            region_groups = Customer.read_group(
                domain=customer_domain,
                fields=['region_id'],
                groupby=['region_id'],
                lazy=False,
            )
        else:
            region_groups = Customer.read_group(
                domain=[('state', '=', 'active')],
                fields=['region_id'],
                groupby=['region_id'],
                lazy=False,
            )
        unassigned_count = Customer.search_count([('state', '=', 'active'), ('region_id', '=', False)])
        for group in region_groups:
            region_value = group.get('region_id')
            rid = region_value[0] if region_value else False
            region_name = region_value[1] if region_value else 'بدون منطقة'
            r_customer_domain = [('state', '=', 'active')]
            if rid:
                r_customer_domain.append(('region_id', '=', rid))
            else:
                r_customer_domain.append(('region_id', '=', False))
            region_customers = Customer.search(r_customer_domain)
            partner_ids = region_customers.mapped('partner_id').ids
            customer_ids = region_customers.ids

            region_prepaid = 0.0
            if pos_orders is not None and customer_ids:
                region_pos_orders = pos_orders.sudo().search([
                    ('date_order', '>=', today_start),
                    ('date_order', '<=', today_end),
                    ('state', 'in', ['paid', 'done', 'invoiced']),
                    ('utility_account_id', 'in', customer_ids),
                ])
                region_prepaid = sum(region_pos_orders.mapped('amount_paid'))

            region_postpaid = 0.0
            if account_payment is not None and partner_ids:
                region_payments = account_payment.sudo().search([
                    ('date', '=', today),
                    ('state', '=', 'posted'),
                    ('payment_type', '=', 'inbound'),
                    ('partner_id', 'in', partner_ids),
                ])
                region_postpaid = sum(region_payments.mapped('amount'))

            region_debt = 0.0
            if account_move is not None and partner_ids:
                region_invoices = account_move.sudo().search([
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial']),
                    ('partner_id', 'in', partner_ids),
                ])
                region_debt = sum(region_invoices.mapped('amount_residual'))

            region_rows.append({
                'region_id': rid,
                'region_name': region_name,
                'active_customers': len(region_customers),
                'today_prepaid': region_prepaid,
                'today_postpaid': region_postpaid,
                'total_debt': region_debt,
                'partner_ids': partner_ids,
            })

        region_rows.sort(key=lambda row: row['active_customers'], reverse=True)

        return {
            'today_prepaid': prepaid_total,
            'today_postpaid': postpaid_total,
            'total_debt': total_debt,
            'active_customers': total_customers,
            'chart_labels': labels,
            'chart_invoices': invoices_data,
            'chart_collections': collections_data,
            'region_rows': region_rows,
            'region_chart_labels': [row['region_name'] for row in region_rows],
            'region_chart_customers': [row['active_customers'] for row in region_rows],
            'region_chart_debt': [row['total_debt'] for row in region_rows],
            'unassigned_customers': unassigned_count,
        }
