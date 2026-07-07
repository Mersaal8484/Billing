from odoo import api, fields, models, _


class UtilityTariffHistory(models.Model):
    _name = 'utility.tariff.history'
    _description = 'Tariff Change History'
    _order = 'change_date desc, id desc'
    _log_access = False

    tariff_id = fields.Many2one('utility.tariff', string='Tariff', required=True, index=True,
                                ondelete='cascade')
    account_id = fields.Many2one('utility.account', string='Account', index=True)
    change_date = fields.Datetime(string='Change Date', default=fields.Datetime.now, required=True, index=True)

    old_price = fields.Monetary(string='Old Price per kWh', digits=(16, 6))
    new_price = fields.Monetary(string='New Price per kWh', digits=(16, 6))
    old_fixed_charge = fields.Monetary(string='Old Fixed Charge')
    new_fixed_charge = fields.Monetary(string='New Fixed Charge')
    old_service_charge = fields.Monetary(string='Old Service Charge')
    new_service_charge = fields.Monetary(string='New Service Charge')

    reason = fields.Text(string='Change Reason', required=True)
    changed_by = fields.Many2one('res.users', string='Changed By', default=lambda self: self.env.user)

    currency_id = fields.Many2one('res.currency', related='tariff_id.currency_id')
