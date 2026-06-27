from odoo import api, fields, models, _


class UtilityPaymentAllocation(models.Model):
    _name = 'utility.payment.allocation'
    _description = 'Utility Payment Allocation'
    _order = 'allocation_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    collection_id = fields.Many2one('utility.collection', 'Collection', required=True)
    bill_id = fields.Many2one('utility.bill', 'Bill', required=True)
    amount_allocated = fields.Float('Amount Allocated')
    allocation_date = fields.Datetime('Allocation Date', default=fields.Datetime.now)
