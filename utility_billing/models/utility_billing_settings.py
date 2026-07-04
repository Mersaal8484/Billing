from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # --- Billing & Invoicing ---
    enable_auto_invoice_confirm = fields.Boolean(
        string='تأكيد الفواتير تلقائياً',
        config_parameter='utility.enable_auto_invoice_confirm',
        default=False)
    auto_generate_bills = fields.Boolean(
        string='توليد الفواتير تلقائياً',
        config_parameter='utility.auto_generate_bills',
        default=True)
    billing_due_days = fields.Integer(
        string='أيام الاستحقاق',
        config_parameter='utility.billing_due_days',
        default=30)
    late_penalty_percentage = fields.Float(
        string='نسبة غرامة التأخير (%)',
        config_parameter='utility.late_penalty_percentage',
        default=1.5)
