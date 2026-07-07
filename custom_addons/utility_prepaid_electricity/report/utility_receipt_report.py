from odoo import api, models


class ReportUtilityReceipt(models.AbstractModel):
    _name = 'report.utility_prepaid_electricity.report_utility_receipt'
    _description = 'Prepaid Electricity Receipt'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['utility.sale'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'utility.sale',
            'docs': docs,
            'data': data,
        }
