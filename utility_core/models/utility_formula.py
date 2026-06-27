import logging
from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class UtilityFormula(models.Model):
    _name = 'utility.formula'
    _description = 'Utility Formula for Contract Lines'
    _rec_name = 'name'

    name = fields.Char('اسم المعادلة', required=True, translate=True)
    code = fields.Text('كود المعادلة', required=True,
        help='كود Python يتم تنفيذه لحساب الكمية.\n'
             'المتغيرات المتاحة:\n'
             '- consumption: float - الاستهلاك (kWh)\n'
             '- previous_reading: float - القراءة السابقة\n'
             '- current_reading: float - القراءة الحالية\n'
             '- tariff: object - كائن التعرفة\n'
             '- account: object - كائن الحساب\n'
             '- category: object - كائن فئة المشترك\n'
             '- line: object - كائن بند العقد الحالي\n'
             '- result: float - يجب تعيينها بقيمة الكمية المحسوبة\n'
             '- name: str - يمكن تغييرها لوصف مخصص')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    def execute(self, consumption=0, previous_reading=0, current_reading=0,
                tariff=None, account=None, category=None, line=None):
        """تنفيذ المعادلة مع المتغيرات الممررة"""
        self.ensure_one()
        result = 0.0
        name = self.name
        
        # متغيرات السياق
        locals_dict = {
            'consumption': consumption or 0.0,
            'previous_reading': previous_reading or 0.0,
            'current_reading': current_reading or 0.0,
            'tariff': tariff,
            'account': account,
            'category': category,
            'line': line,
            'result': result,
            'name': name,
        }
        
        try:
            safe_eval(self.code, mode='exec', locals_dict=locals_dict, nocopy=True)
            result = locals_dict.get('result', 0.0)
            name = locals_dict.get('name', self.name)
        except Exception as e:
            _logger.warning("Formula execution error in %s: %s", self.name, e)
            result = 0.0
        
        return result, name
