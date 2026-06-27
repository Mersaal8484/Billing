from odoo import models


class ReportUtilityReceipt(models.AbstractModel):
    _name = 'report.utility_prepaid.report_utility_receipt'

    def _get_report_values(self, docids, data=None):
        docs = self.env['utility.sale'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'utility.sale',
            'docs': docs,
        }
