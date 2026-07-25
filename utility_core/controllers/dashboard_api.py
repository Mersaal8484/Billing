from odoo import http, fields
from odoo.http import request
from datetime import datetime, timedelta


class UtilityDashboardAPI(http.Controller):

    @http.route('/utility/dashboard/kpi', type='json', auth='user')
    def get_kpis(self, region_id=False):
        """
        لوحة قيادة مخصصة حصرياً لبيانات الفوترة والتحصيل الآجل (Postpaid Billing)
        بدون إدخال أي من مبيعات أو معاملات الدفع المسبق (Prepaid/POS).
        """
        if not request.env.user.has_group('base.group_system'):
            return {'error': 'Access denied. Dashboard is restricted to internal administrators.'}

        today = fields.Date.context_today(request.env.user)
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        # 1. Base Postpaid Customer Domain
        customer_domain = [('state', '=', 'active')]
        if region_id:
            customer_domain.append(('region_id', '=', region_id))

        Customer = request.env['utility.customer'].sudo()
        customers = Customer.search(customer_domain)
        partner_ids = customers.mapped('partner_id').ids
        customer_ids = customers.ids
        total_postpaid_customers = len(customers)

        # 2. Today's Postpaid Collections
        postpaid_collections_today = 0.0
        account_payment = request.env.get('account.payment')
        if account_payment is not None and partner_ids:
            pay_data = account_payment.sudo().read_group([
                ('date', '=', today),
                ('state', '=', 'posted'),
                ('payment_type', '=', 'inbound'),
                ('partner_id', 'in', partner_ids),
            ], ['amount:sum'], [])
            postpaid_collections_today = pay_data[0].get('amount', 0) if pay_data else 0.0

        # 3. Today's Billed Postpaid Sales
        postpaid_billed_today = 0.0
        sale_order = request.env.get('sale.order')
        if sale_order is not None and customer_ids:
            so_data = sale_order.sudo().read_group([
                ('create_date', '>=', today_start),
                ('create_date', '<=', today_end),
                ('customer_id', 'in', customer_ids),
                ('state', 'in', ['sale', 'done']),
            ], ['amount_total:sum'], [])
            postpaid_billed_today = so_data[0].get('amount_total', 0) if so_data else 0.0

        # 4. Total Outstanding Debt & Overdue Debt
        total_debt = 0.0
        overdue_debt = 0.0
        overdue_count = 0

        if sale_order is not None and customer_ids:
            open_orders = sale_order.sudo().search([
                ('customer_id', 'in', customer_ids),
                ('bill_state', 'in', ['confirmed', 'sent', 'overdue']),
                ('balance_due', '>', 0),
            ])
            total_debt = sum(open_orders.mapped('balance_due'))
            overdue_orders = open_orders.filtered(lambda r: r.bill_state == 'overdue' or r.is_overdue)
            overdue_debt = sum(overdue_orders.mapped('balance_due'))
            overdue_count = len(overdue_orders)

        # 5. Last 7 Days: aggregate via read_group instead of per-day loops
        seven_days_ago = today - timedelta(days=6)
        d_start_week = datetime.combine(seven_days_ago, datetime.min.time())
        invoices_data = [0.0] * 7
        collections_data = [0.0] * 7
        labels = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]

        if sale_order is not None and customer_ids:
            billed_groups = sale_order.sudo().read_group([
                ('create_date', '>=', d_start_week),
                ('create_date', '<=', today_end),
                ('customer_id', 'in', customer_ids),
                ('state', 'in', ['sale', 'done']),
            ], ['amount_total:sum'], ['create_date:day'])
            for g in billed_groups:
                date_key = (
                    g.get('__range', {}).get('create_date:day', {}).get('from', '')[:10]
                )
                if date_key in labels:
                    invoices_data[labels.index(date_key)] = g.get('amount_total', 0)

        if account_payment is not None and partner_ids:
            pay_groups = account_payment.sudo().read_group([
                ('date', '>=', seven_days_ago),
                ('date', '<=', today),
                ('state', '=', 'posted'),
                ('payment_type', '=', 'inbound'),
                ('partner_id', 'in', partner_ids),
            ], ['amount:sum'], ['date:day'])
            for g in pay_groups:
                date_key = (
                    g.get('__range', {}).get('date:day', {}).get('from', '')[:10]
                )
                if date_key in labels:
                    collections_data[labels.index(date_key)] = g.get('amount', 0)

        # 6. Region-level Postpaid Performance via read_group
        region_rows = []
        region_groups = Customer.read_group(
            domain=[('state', '=', 'active')] + ([('region_id', '=', region_id)] if region_id else []),
            fields=['region_id'],
            groupby=['region_id'],
            lazy=False,
        )

        region_partner_map = {}
        region_customer_map = {}
        for group in region_groups:
            region_value = group.get('region_id')
            rid = region_value[0] if region_value else False
            region_name = region_value[1] if region_value else 'غير محدد'
            r_customers = Customer.search([('state', '=', 'active'), ('region_id', '=', rid)])
            r_partner_ids = r_customers.mapped('partner_id').ids
            r_customer_ids = r_customers.ids
            region_partner_map[rid] = r_partner_ids
            region_customer_map[rid] = r_customer_ids
            region_rows.append({
                'region_id': rid,
                'region_name': region_name,
                'active_customers': len(r_customers),
                'today_postpaid': 0.0,
                'today_billed': 0.0,
                'total_debt': 0.0,
                'overdue_debt': 0.0,
                'partner_ids': r_partner_ids,
            })

        if region_rows:
            all_r_partner_ids = []
            all_r_customer_ids = []
            for row in region_rows:
                all_r_partner_ids.extend(row['partner_ids'])
                all_r_customer_ids.extend(region_customer_map.get(row['region_id'], []))
            all_r_partner_ids = list(set(all_r_partner_ids))
            all_r_customer_ids = list(set(all_r_customer_ids))

            if account_payment is not None and all_r_partner_ids:
                r_partner_to_region = {}
                for row in region_rows:
                    for pid in row['partner_ids']:
                        r_partner_to_region[pid] = row['region_id']
                r_pay_groups = account_payment.sudo().read_group([
                    ('date', '=', today),
                    ('state', '=', 'posted'),
                    ('payment_type', '=', 'inbound'),
                    ('partner_id', 'in', all_r_partner_ids),
                ], ['amount:sum'], ['partner_id'])
                for g in r_pay_groups:
                    pid = g['partner_id'][0] if g['partner_id'] else False
                    rid = r_partner_to_region.get(pid)
                    for row in region_rows:
                        if row['region_id'] == rid:
                            row['today_postpaid'] += g.get('amount', 0)
                            break

            if sale_order is not None and all_r_customer_ids:
                r_so_to_region = {}
                for row in region_rows:
                    for cid in region_customer_map.get(row['region_id'], []):
                        r_so_to_region[cid] = row['region_id']
                r_billed_groups = sale_order.sudo().read_group([
                    ('create_date', '>=', today_start),
                    ('create_date', '<=', today_end),
                    ('customer_id', 'in', all_r_customer_ids),
                    ('state', 'in', ['sale', 'done']),
                ], ['amount_total:sum'], ['customer_id'])
                for g in r_billed_groups:
                    cid = g['customer_id'][0] if g['customer_id'] else False
                    rid = r_so_to_region.get(cid)
                    for row in region_rows:
                        if row['region_id'] == rid:
                            row['today_billed'] += g.get('amount_total', 0)
                            break

                r_open_orders = sale_order.sudo().search([
                    ('customer_id', 'in', all_r_customer_ids),
                    ('bill_state', 'in', ['confirmed', 'sent', 'overdue']),
                    ('balance_due', '>', 0),
                ])
                for row in region_rows:
                    rcids = set(region_customer_map.get(row['region_id'], []))
                    r_open = r_open_orders.filtered(lambda o: o.customer_id.id in rcids)
                    row['total_debt'] = sum(r_open.mapped('balance_due'))
                    row['overdue_debt'] = sum(
                        r_open.filtered(lambda r: r.bill_state == 'overdue' or r.is_overdue).mapped('balance_due'))

        region_rows.sort(key=lambda r: r['total_debt'], reverse=True)

        return {
            'today_postpaid': postpaid_collections_today,
            'today_billed': postpaid_billed_today,
            'total_debt': total_debt,
            'overdue_debt': overdue_debt,
            'overdue_count': overdue_count,
            'active_customers': total_postpaid_customers,
            'chart_labels': labels,
            'chart_invoices': invoices_data,
            'chart_collections': collections_data,
            'region_rows': region_rows,
            'region_chart_labels': [row['region_name'] for row in region_rows],
            'region_chart_customers': [row['active_customers'] for row in region_rows],
            'region_chart_debt': [row['total_debt'] for row in region_rows],
        }