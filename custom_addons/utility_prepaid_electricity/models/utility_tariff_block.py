from odoo import fields, models


class UtilityTariffBlock(models.Model):
    _name = 'utility.tariff.block'
    _description = 'Tariff Pricing Block'
    _order = 'tariff_id, sequence'

    active = fields.Boolean(default=True)
    tariff_id = fields.Many2one('utility.tariff', string='Tariff', required=True, index=True,
                                ondelete='cascade')

    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Block Name', required=True)

    from_kwh = fields.Float(string='From kWh', default=0.0, required=True)
    to_kwh = fields.Float(string='To kWh', help='Leave empty for unlimited')
    price_per_kwh = fields.Monetary(string='Price per kWh', digits=(16, 6), required=True)
    currency_id = fields.Many2one('res.currency', related='tariff_id.currency_id')

    from_month = fields.Integer(string='From Month', help='Month number (1-12) for seasonal')
    to_month = fields.Integer(string='To Month', help='Month number (1-12) for seasonal')

    time_from = fields.Float(string='Time From', help='Hour (0-24) for TOU')
    time_to = fields.Float(string='Time To', help='Hour (0-24) for TOU')

    _sql_constraints = [
        ('check_kwh_range', 'CHECK(from_kwh >= 0 AND (to_kwh IS NULL OR to_kwh > from_kwh))',
         'kWh range must be valid!'),
        ('check_month_range', 'CHECK(from_month IS NULL OR (from_month >= 1 AND from_month <= 12))',
         'Month must be between 1 and 12!'),
        ('check_time_range', 'CHECK(time_from IS NULL OR (time_from >= 0 AND time_from <= 24))',
         'Time must be between 0 and 24!'),
    ]
