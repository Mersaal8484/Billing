from odoo import api, fields, models


class UtilityDashboard(models.Model):
    _name = 'utility.dashboard'
    _description = 'Utility Dashboard KPI'
    _auto = False
    _log_access = False

    date = fields.Date(string='Date', readonly=True)
    region_id = fields.Many2one('utility.region', string='Region', readonly=True)
    area_id = fields.Many2one('utility.area', string='Service Area', readonly=True)
    tariff_id = fields.Many2one('utility.tariff', string='Tariff', readonly=True)

    total_customers = fields.Integer(string='Total Customers', readonly=True)
    active_customers = fields.Integer(string='Active Customers', readonly=True)
    disconnected_customers = fields.Integer(string='Disconnected', readonly=True)
    total_accounts = fields.Integer(string='Total Accounts', readonly=True)
    total_meters = fields.Integer(string='Total Meters', readonly=True)

    today_sales_count = fields.Integer(string="Today's Sales", readonly=True)
    today_revenue = fields.Monetary(string="Today's Revenue", readonly=True)
    today_kwh = fields.Float(string="Today's kWh Sold", readonly=True)

    total_revenue = fields.Monetary(string='Total Revenue', readonly=True)
    total_kwh = fields.Float(string='Total kWh Sold', readonly=True)

    failed_transactions = fields.Integer(string='Failed Transactions', readonly=True)
    low_credit_accounts = fields.Integer(string='Low Credit Accounts', readonly=True)
    zero_credit_accounts = fields.Integer(string='Zero Credit Accounts', readonly=True)
    active_alarms = fields.Integer(string='Active Alarms', readonly=True)

    avg_balance = fields.Monetary(string='Avg Balance', readonly=True)
    emergency_credit_total = fields.Monetary(string='Emergency Credit Total', readonly=True)

    currency_id = fields.Many2one('res.currency', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW utility_dashboard AS (
                WITH customer_stats AS (
                    SELECT
                        c.region_id,
                        c.area_id,
                        COUNT(*) AS total_customers,
                        COUNT(*) FILTER (WHERE c.connection_status = 'active') AS active_customers,
                        COUNT(*) FILTER (WHERE c.connection_status = 'disconnected') AS disconnected_customers
                    FROM utility_customer c
                    WHERE c.active = true
                    GROUP BY c.region_id, c.area_id
                ),
                account_stats AS (
                    SELECT
                        a.region_id,
                        a.area_id,
                        a.tariff_id,
                        COUNT(*) AS total_accounts,
                        COALESCE(AVG(a.balance), 0) AS avg_balance,
                        COALESCE(SUM(a.emergency_credit), 0) AS emergency_credit_total,
                        COUNT(*) FILTER (WHERE a.balance > 0 AND a.balance < 50) AS low_credit_accounts,
                        COUNT(*) FILTER (WHERE a.balance <= 0) AS zero_credit_accounts
                    FROM utility_account a
                    WHERE a.active = true AND a.state = 'active'
                    GROUP BY a.region_id, a.area_id, a.tariff_id
                ),
                meter_stats AS (
                    SELECT m.region_id, m.area_id, COUNT(*) AS total_meters
                    FROM utility_meter m
                    WHERE m.active = true
                    GROUP BY m.region_id, m.area_id
                ),
                today_sales AS (
                    SELECT
                        s.region_id,
                        s.area_id,
                        s.tariff_id,
                        COUNT(*) AS today_sales_count,
                        COALESCE(SUM(s.amount_paid), 0) AS today_revenue,
                        COALESCE(SUM(s.kwh_purchased), 0) AS today_kwh
                    FROM utility_sale s
                    WHERE s.date::date = CURRENT_DATE AND s.state NOT IN ('cancelled', 'reversed')
                    GROUP BY s.region_id, s.area_id, s.tariff_id
                ),
                total_sales AS (
                    SELECT
                        s.region_id,
                        s.area_id,
                        s.tariff_id,
                        COALESCE(SUM(s.amount_paid), 0) AS total_revenue,
                        COALESCE(SUM(s.kwh_purchased), 0) AS total_kwh
                    FROM utility_sale s
                    WHERE s.state NOT IN ('cancelled', 'reversed')
                    GROUP BY s.region_id, s.area_id, s.tariff_id
                ),
                failed_tx AS (
                    SELECT s.region_id, s.area_id,
                        COUNT(*) AS failed_transactions
                    FROM utility_sale s
                    WHERE s.token_status = 'failed'
                    GROUP BY s.region_id, s.area_id
                ),
                alarm_stats AS (
                    SELECT a.region_id, a.area_id,
                        COUNT(*) AS active_alarms
                    FROM utility_alarm a
                    WHERE a.state NOT IN ('resolved', 'closed')
                    GROUP BY a.region_id, a.area_id
                )
                SELECT
                    row_number() OVER () AS id,
                    CURRENT_DATE AS date,
                    COALESCE(cs.region_id, acs.region_id, ms.region_id,
                             ts.region_id, ftx.region_id, als.region_id) AS region_id,
                    COALESCE(cs.area_id, acs.area_id, ms.area_id,
                             ts.area_id, ftx.area_id, als.area_id) AS area_id,
                    COALESCE(acs.tariff_id, ts.tariff_id) AS tariff_id,
                    COALESCE(cs.total_customers, 0) AS total_customers,
                    COALESCE(cs.active_customers, 0) AS active_customers,
                    COALESCE(cs.disconnected_customers, 0) AS disconnected_customers,
                    COALESCE(acs.total_accounts, 0) AS total_accounts,
                    COALESCE(ms.total_meters, 0) AS total_meters,
                    COALESCE(ts.today_sales_count, 0) AS today_sales_count,
                    COALESCE(ts.today_revenue, 0) AS today_revenue,
                    COALESCE(ts.today_kwh, 0) AS today_kwh,
                    COALESCE(tot.total_revenue, 0) AS total_revenue,
                    COALESCE(tot.total_kwh, 0) AS total_kwh,
                    COALESCE(ftx.failed_transactions, 0) AS failed_transactions,
                    COALESCE(acs.low_credit_accounts, 0) AS low_credit_accounts,
                    COALESCE(acs.zero_credit_accounts, 0) AS zero_credit_accounts,
                    COALESCE(als.active_alarms, 0) AS active_alarms,
                    COALESCE(acs.avg_balance, 0) AS avg_balance,
                    COALESCE(acs.emergency_credit_total, 0) AS emergency_credit_total,
                    acs.company_id
                FROM customer_stats cs
                FULL JOIN account_stats acs ON cs.region_id = acs.region_id AND cs.area_id = acs.area_id
                FULL JOIN meter_stats ms ON COALESCE(cs.region_id, acs.region_id) = ms.region_id
                    AND COALESCE(cs.area_id, acs.area_id) = ms.area_id
                FULL JOIN today_sales ts ON COALESCE(cs.region_id, acs.region_id, ms.region_id) = ts.region_id
                    AND COALESCE(cs.area_id, acs.area_id, ms.area_id) = ts.area_id
                FULL JOIN total_sales tot ON COALESCE(cs.region_id, acs.region_id, ms.region_id, ts.region_id) = tot.region_id
                    AND COALESCE(cs.area_id, acs.area_id, ms.area_id, ts.area_id) = tot.area_id
                FULL JOIN failed_tx ftx ON COALESCE(cs.region_id, acs.region_id, ms.region_id, ts.region_id, tot.region_id) = ftx.region_id
                    AND COALESCE(cs.area_id, acs.area_id, ms.area_id, ts.area_id, tot.area_id) = ftx.area_id
                FULL JOIN alarm_stats als ON COALESCE(cs.region_id, acs.region_id, ms.region_id, ts.region_id, tot.region_id, ftx.region_id) = als.region_id
                    AND COALESCE(cs.area_id, acs.area_id, ms.area_id, ts.area_id, tot.area_id, ftx.area_id) = als.area_id
            )
        """)


class UtilityReport(models.Model):
    _name = 'utility.report'
    _description = 'Utility Report Configuration'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)

    name = fields.Char(string='Report Name', required=True, translate=True)
    report_type = fields.Selection([
        ('daily_sales', 'Daily Sales'),
        ('monthly_sales', 'Monthly Sales'),
        ('revenue', 'Revenue'),
        ('energy_sold', 'Energy Sold'),
        ('operator_performance', 'Operator Performance'),
        ('area_performance', 'Area Performance'),
        ('transformer_sales', 'Transformer Sales'),
        ('feeder_sales', 'Feeder Sales'),
        ('customer_statement', 'Customer Statement'),
        ('meter_history', 'Meter History'),
        ('tariff_analysis', 'Tariff Analysis'),
        ('failed_transactions', 'Failed Transactions'),
        ('reversals', 'Reversals'),
        ('audit_report', 'Audit Report'),
        ('collection_report', 'Collection Report'),
    ], string='Report Type', required=True, index=True)

    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date')
    region_id = fields.Many2one('utility.region', string='Region')
    area_id = fields.Many2one('utility.area', string='Service Area')
    tariff_id = fields.Many2one('utility.tariff', string='Tariff')
    operator_id = fields.Many2one('res.users', string='Operator')

    report_data = fields.Text(string='Report Data (JSON)')
    generated_date = fields.Datetime(string='Generated Date')

    def action_generate(self):
        """Generate report data based on type and filters."""
        self.ensure_one()
        # Report generation logic - implemented in service layer
        return True
