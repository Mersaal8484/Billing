from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMeterReplaceWizard(models.TransientModel):
    _name = 'utility.meter.replace.wizard'
    _inherit = ['utility.dropdown.mixin']
    _description = 'معالج استبدال العداد'

    account_id = fields.Many2one('utility.customer', 'حساب الكهرباء', required=True)
    old_meter_id = fields.Many2one('utility.meter', 'العداد القديم', related='account_id.meter_id', readonly=True)
    available_new_meter_ids = fields.Many2many('utility.meter', compute='_compute_available_new_meter_ids')
    new_meter_id = fields.Many2one('utility.meter', 'العداد الجديد', required=True, domain="[('id', 'in', available_new_meter_ids)]")
    
    old_meter_final_reading = fields.Float('القراءة النهائية للقديم', required=True)
    new_meter_initial_reading = fields.Float('القراءة الابتدائية للجديد', default=0.0, required=True)
    reason = fields.Text('سبب الاستبدال')

    @api.depends('account_id')
    def _compute_available_new_meter_ids(self):
        domain = self._get_available_new_meter_domain()
        meters = self.env['utility.meter'].search(domain)
        for rec in self:
            rec.available_new_meter_ids = meters

    def action_execute_replacement(self):
        self.ensure_one()
        replacement = self.env['utility.meter.replacement'].create({
            'utility_account_id': self.account_id.id,
            'old_meter_id': self.old_meter_id.id,
            'new_meter_id': self.new_meter_id.id,
            'old_meter_final_reading': self.old_meter_final_reading,
            'new_meter_initial_reading': self.new_meter_initial_reading,
            'reason': self.reason,
        })
        replacement.action_complete_replacement()
        return True
