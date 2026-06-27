from odoo import api, models, _


class ReportUtilityReceipt(models.AbstractModel):
    _name = 'report.utility_core.receipt_report'
    _description = 'Utility Receipt Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['utility.customer'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'utility.customer',
            'docs': docs,
            'data': data,
        }
