from odoo import api, models, _


class ReportConstructionIpc(models.AbstractModel):
    _name = 'report.construction_execution.report_construction_ipc'
    _description = 'IPC Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['construction.ipc'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'construction.ipc',
            'docs': docs,
            'data': data,
        }
