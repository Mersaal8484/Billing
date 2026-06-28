from odoo import api, models, _


class ReportConstructionProgress(models.AbstractModel):
    _name = 'report.construction_execution.report_construction_progress'
    _description = 'Progress Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['construction.progress'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'construction.progress',
            'docs': docs,
            'data': data,
        }
