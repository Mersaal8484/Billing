from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMeterReplaceWizard(models.TransientModel):
    _name = 'utility.meter.replace.wizard'
    _description = 'Meter Replacement Wizard'

    account_id = fields.Many2one('utility.customer', 'حساب الكهرباء', required=True)
    old_meter_id = fields.Many2one('utility.meter', 'العداد القديم', related='account_id.meter_id', readonly=True)
    new_meter_id = fields.Many2one('utility.meter', 'العداد الجديد', required=True, domain="[('customer_id', '=', False), ('active', '=', True)]")
    
    old_meter_final_reading = fields.Float('القراءة النهائية للقديم', required=True)
    new_meter_initial_reading = fields.Float('القراءة الابتدائية للجديد', default=0.0, required=True)
    reason = fields.Text('سبب الاستبدال')

    def action_execute_replacement(self):
        self.ensure_one()
        replacement = self.env['utility.meter.replacement'].create({
            'account_id': self.account_id.id,
            'old_meter_id': self.old_meter_id.id,
            'new_meter_id': self.new_meter_id.id,
            'old_meter_final_reading': self.old_meter_final_reading,
            'new_meter_initial_reading': self.new_meter_initial_reading,
            'reason': self.reason,
        })
        replacement.action_complete_replacement()
        return True
