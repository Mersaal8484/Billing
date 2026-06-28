from odoo import api, fields, models


class PropertyDashboard(models.Model):
    _name = 'property.dashboard'
    _description = 'Property Dashboard'
    _auto = False
    _log_access = False

    property_id = fields.Many2one('property.property', string='Property', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    total_units = fields.Integer(string='Total Units', readonly=True)
    occupied_units = fields.Integer(string='Occupied', readonly=True)
    vacant_units = fields.Integer(string='Vacant', readonly=True)
    occupancy_rate = fields.Float(string='Occupancy %', readonly=True, digits=(5, 2))
    annual_rent_income = fields.Monetary(string='Annual Rent', readonly=True)
    total_maintenance_cost = fields.Monetary(string='Maintenance Cost', readonly=True)
    net_operating_income = fields.Monetary(string='NOI', readonly=True)
    property_value = fields.Monetary(string='Property Value', readonly=True)
    total_receivables = fields.Monetary(string='Outstanding Receivables', readonly=True)
    expected_cashflow_30d = fields.Monetary(string='Expected Cashflow (30d)', readonly=True)
    expiring_leases_30d = fields.Integer(string='Expiring Leases (30d)', readonly=True)
    maintenance_open_count = fields.Integer(string='Open Maintenance Requests', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE or REPLACE VIEW property_dashboard AS (
                SELECT
                    row_number() OVER () AS id,
                    p.id AS property_id,
                    CURRENT_DATE AS date,
                    p.total_units,
                    p.occupied_units,
                    p.vacant_units,
                    p.occupancy_rate,
                    p.annual_rent_income,
                    p.total_maintenance_cost,
                    p.net_operating_income,
                    p.property_value,
                    COALESCE((SELECT SUM(amount_residual) FROM account_move WHERE move_type = 'out_invoice' AND state = 'posted' AND payment_state IN ('not_paid', 'partial') AND partner_id IN (SELECT partner_id FROM property_tenant WHERE id IN (SELECT current_tenant_id FROM property_unit WHERE property_id = p.id))), 0.0) AS total_receivables,
                    COALESCE((SELECT SUM(remaining) FROM property_payment_schedule WHERE property_id = p.id AND state IN ('pending', 'partial') AND date <= CURRENT_DATE + 30), 0.0) AS expected_cashflow_30d,
                    (SELECT COUNT(*) FROM property_lease WHERE property_id = p.id AND state = 'active' AND end_date <= CURRENT_DATE + 30) AS expiring_leases_30d,
                    (SELECT COUNT(*) FROM property_maintenance WHERE property_id = p.id AND state IN ('submitted', 'approved', 'in_progress')) AS maintenance_open_count,
                    c.currency_id,
                    p.company_id
                FROM property_property p
                LEFT JOIN res_company c ON p.company_id = c.id
                WHERE p.active = true
            )
        """)

