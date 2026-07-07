from odoo import fields, models


class UtilityMeterType(models.Model):
    _name = 'utility.meter.type'
    _description = 'Meter Type'
    _order = 'sequence, name'

    name = fields.Char(string='Meter Type', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    phase = fields.Selection([
        ('single', 'Single Phase'),
        ('three', 'Three Phase'),
        ('both', 'Single & Three Phase'),
    ], string='Supported Phase', default='both')

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Meter type code must be unique!'),
    ]


class UtilityMeterStatus(models.Model):
    _name = 'utility.meter.status'
    _description = 'Meter Status'
    _order = 'sequence, name'

    name = fields.Char(string='Status Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Meter status code must be unique!'),
    ]
