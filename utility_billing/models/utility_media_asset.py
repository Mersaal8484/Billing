from odoo import fields, models


class UtilityMediaAsset(models.Model):
    _inherit = 'utility.media.asset'

    batch_id = fields.Many2one(
        'utility.reading.batch',
        string='الدفعة المرتبطة',
        index=True,
        ondelete='set null'
    )
