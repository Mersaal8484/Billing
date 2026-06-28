from odoo import api, fields, models, _


class ConstructionBoqImportWizard(models.TransientModel):
    _name = 'construction.boq.import.wizard'
    _description = 'Import BOQ Items Wizard'

    boq_id = fields.Many2one('construction.boq', string='BOQ', required=True)
    data = fields.Text(string='Import Data (CSV)', required=True,
                       help='Paste CSV data: Code,Description,Unit,Qty,Rate')

    def action_import(self):
        self.ensure_one()
        lines = self.data.strip().split('\n')
        created = 0
        for line in lines:
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 5:
                code, name, unit_name, qty, rate = parts[:5]
                uom = self.env['uom.uom'].search([('name', '=', unit_name)], limit=1)
                if not uom:
                    uom = self.env.ref('uom.product_uom_unit')
                self.env['construction.boq.item'].create({
                    'boq_id': self.boq_id.id,
                    'code': code,
                    'name': name,
                    'unit': uom.id,
                    'quantity': float(qty or 0),
                    'rate': float(rate or 0),
                })
                created += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


class ConstructionProgressGenerateWizard(models.TransientModel):
    _name = 'construction.progress.generate.wizard'
    _description = 'Generate Progress Lines Wizard'

    progress_id = fields.Many2one('construction.progress', string='Progress',
                                  required=True)
    include_completed = fields.Boolean(string='Include Completed Items', default=False)

    def action_generate(self):
        self.ensure_one()
        self.progress_id.action_generate_lines()
        return {'type': 'ir.actions.client', 'tag': 'reload'}


class ConstructionIpcGenerateWizard(models.TransientModel):
    _name = 'construction.ipc.generate.wizard'
    _description = 'Generate IPC Lines from Progress'

    ipc_id = fields.Many2one('construction.ipc', string='IPC', required=True)
    project_id = fields.Many2one('construction.project', string='Project',
                                 related='ipc_id.project_id', readonly=True)
    progress_id = fields.Many2one('construction.progress', string='From Progress',
                                  required=True)

    def action_generate(self):
        self.ensure_one()
        progress = self.progress_id
        ipc = self.ipc_id
        for line in progress.line_ids:
            self.env['construction.ipc.line'].create({
                'ipc_id': ipc.id,
                'boq_item_id': line.boq_item_id.id,
                'previous_quantity': line.previous_quantity,
                'current_quantity': line.current_quantity,
                'rate': line.unit_rate,
            })
        return {'type': 'ir.actions.client', 'tag': 'reload'}
