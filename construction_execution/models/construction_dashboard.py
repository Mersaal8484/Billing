from odoo import api, fields, models, _


class ConstructionDashboard(models.Model):
    _name = 'construction.dashboard'
    _description = 'Construction Dashboard KPI'
    _order = 'date desc'
    _auto = False
    _log_access = False

    project_id = fields.Many2one('construction.project', string='Project', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    project_value = fields.Monetary(string='Project Value', readonly=True)
    executed_value = fields.Monetary(string='Executed Value', readonly=True)
    remaining_value = fields.Monetary(string='Remaining Value', readonly=True)
    budget_cost = fields.Monetary(string='Budget Cost', readonly=True)
    actual_cost = fields.Monetary(string='Actual Cost', readonly=True)
    forecast_cost = fields.Monetary(string='Forecast Cost', readonly=True)
    cost_variance = fields.Monetary(string='Cost Variance', readonly=True)
    progress_percent = fields.Float(string='Progress %', readonly=True,
                                    digits=(5, 2))
    spi = fields.Float(string='SPI', readonly=True, digits=(12, 4))
    cpi = fields.Float(string='CPI', readonly=True, digits=(12, 4))
    eac = fields.Monetary(string='EAC', readonly=True)
    etc = fields.Monetary(string='ETC', readonly=True)
    vac = fields.Monetary(string='VAC', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE or REPLACE VIEW construction_dashboard AS (
                SELECT
                    row_number() OVER () AS id,
                    p.id AS project_id,
                    CURRENT_DATE AS date,
                    p.contract_amount AS project_value,
                    COALESCE((
                        SELECT SUM(ipc.total_approved_amount)
                        FROM construction_ipc ipc
                        WHERE ipc.project_id = p.id
                        AND ipc.state IN ('certified','approved','paid')
                    ), 0.0) AS executed_value,
                    p.contract_amount - COALESCE((
                        SELECT SUM(ipc.total_approved_amount)
                        FROM construction_ipc ipc
                        WHERE ipc.project_id = p.id
                        AND ipc.state IN ('certified','approved','paid')
                    ), 0.0) AS remaining_value,
                    COALESCE((
                        SELECT SUM(b.grand_total)
                        FROM construction_budget b
                        WHERE b.project_id = p.id AND b.state = 'approved'
                    ), 0.0) AS budget_cost,
                    COALESCE((
                        SELECT SUM(ce.amount)
                        FROM construction_cost_entry ce
                        WHERE ce.project_id = p.id
                    ), 0.0) AS actual_cost,
                    COALESCE((
                        SELECT SUM(f.forecast_amount)
                        FROM construction_forecast f
                        WHERE f.project_id = p.id
                        AND f.forecast_type = 'cost'
                    ), 0.0) AS forecast_cost,
                    COALESCE((
                        SELECT SUM(b.grand_total)
                        FROM construction_budget b
                        WHERE b.project_id = p.id AND b.state = 'approved'
                    ), 0.0) - COALESCE((
                        SELECT SUM(ce.amount)
                        FROM construction_cost_entry ce
                        WHERE ce.project_id = p.id
                    ), 0.0) AS cost_variance,
                    COALESCE(p.progress_percent, 0.0) AS progress_percent,
                    CASE WHEN COALESCE((
                        SELECT SUM(b.grand_total)
                        FROM construction_budget b
                        WHERE b.project_id = p.id AND b.state = 'approved'
                    ), 0.0) > 0
                    THEN COALESCE((
                        SELECT SUM(ipc.total_approved_amount)
                        FROM construction_ipc ipc
                        WHERE ipc.project_id = p.id
                        AND ipc.state IN ('certified','approved','paid')
                    ), 0.0) / COALESCE((
                        SELECT SUM(b.grand_total)
                        FROM construction_budget b
                        WHERE b.project_id = p.id AND b.state = 'approved'
                    ), 1.0) ELSE 0.0 END AS spi,
                    CASE WHEN COALESCE((
                        SELECT SUM(ce.amount)
                        FROM construction_cost_entry ce
                        WHERE ce.project_id = p.id
                    ), 0.0) > 0
                    THEN COALESCE((
                        SELECT SUM(ipc.total_approved_amount)
                        FROM construction_ipc ipc
                        WHERE ipc.project_id = p.id
                        AND ipc.state IN ('certified','approved','paid')
                    ), 0.0) / COALESCE((
                        SELECT SUM(ce.amount)
                        FROM construction_cost_entry ce
                        WHERE ce.project_id = p.id
                    ), 1.0) ELSE 0.0 END AS cpi,
                    0.0 AS eac,
                    0.0 AS etc,
                    0.0 AS vac,
                    c.currency_id,
                    p.company_id
                FROM construction_project p
                LEFT JOIN res_company c ON p.company_id = c.id
                WHERE p.active = true
            )
        """)
