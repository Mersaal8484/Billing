from odoo import api, fields, models, _


class UtilityBillLine(models.Model):
    _name = 'utility.bill.line'
    _description = 'Utility Bill Line'
    _order = 'sequence, id'

    bill_id = fields.Many2one('utility.bill', 'Bill', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', default=10)
    name = fields.Char('Description')
    quantity = fields.Float('Quantity', default=1.0)
    unit = fields.Char('Unit')
    unit_price = fields.Float('Unit Price')
    amount = fields.Float('Amount')
    is_tax = fields.Boolean('Is Tax', default=False)
