from odoo import api, models, _


class ReportConstructionBoq(models.AbstractModel):
    _name = 'report.construction_execution.report_construction_boq'
    _description = 'BOQ Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['construction.boq'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'construction.boq',
            'docs': docs,
            'data': data,
        }

    @api.model
    def render_html(self, docids, data=None):
        return self._get_report_values(docids, data)
