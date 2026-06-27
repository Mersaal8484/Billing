from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    collection_journal_id = fields.Many2one(
        'account.journal', string='اليومية النقدية للتحصيل',
        domain="[('type', 'in', ('cash', 'bank'))]",
        help='اليومية الخاصة بالمحصل لتسجيل دفعات فواتير الكهرباء')
