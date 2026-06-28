from odoo import api, models


class ReportPropertyLease(models.AbstractModel):
    _name = 'report.property_management.report_property_lease'
    _description = 'Lease Contract Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['property.lease'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'property.lease',
            'docs': docs,
            'data': data,
        }
