import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class UtilityFormulaTestWizard(models.TransientModel):
    _name = 'utility.formula.test.wizard'
    _description = 'Formula Test Wizard'

    formula_id = fields.Many2one('utility.formula', 'المعادلة', required=True, readonly=True)
    consumption = fields.Float('الاستهلاك (kWh)', default=100.0)
    previous_reading = fields.Float('القراءة السابقة', default=0.0)
    current_reading = fields.Float('القراءة الحالية', default=100.0)
    result = fields.Float('النتيجة', readonly=True)
    computed_name = fields.Char('الاسم المحسوب', readonly=True)
    error_message = fields.Text('رسالة الخطأ', readonly=True)
    state = fields.Selection([
        ('input', 'إدخال'),
        ('result', 'نتيجة'),
    ], default='input')

    def action_run(self):
        self.ensure_one()
        try:
            result, computed_name = self.formula_id.execute(
                consumption=self.consumption,
                previous_reading=self.previous_reading,
                current_reading=self.current_reading,
            )
            self.result = result
            self.computed_name = computed_name
            self.error_message = False
        except Exception as e:
            self.result = 0.0
            self.computed_name = False
            self.error_message = str(e)
        self.state = 'result'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'utility.formula.test.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_reset(self):
        self.state = 'input'
        self.result = 0.0
        self.computed_name = False
        self.error_message = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'utility.formula.test.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
