from odoo import api, fields, models, _


class UtilityTamperCase(models.Model):
    _name = 'utility.tamper.case'
    _description = 'Utility Tamper Case'
    _rec_name = 'case_number'
    _inherit = ['mail.thread']
    _order = 'date_reported desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    case_number = fields.Char('Case Number', required=True, index=True, default=lambda self: _('New'))
    date_reported = fields.Datetime('Date Reported', default=fields.Datetime.now)
    customer_id = fields.Many2one('utility.customer', 'Customer')
    account_id = fields.Many2one('utility.customer', 'Account', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'Meter')
    tamper_type = fields.Selection([
        ('meter_bypass', 'Meter Bypass'),
        ('meter_tamper', 'Meter Tamper'),
        ('meter_reversal', 'Meter Reversal'),
        ('unauthorized_connection', 'Unauthorized Connection'),
        ('meter_removal', 'Meter Removal'),
        ('other', 'Other'),
    ], string='Tamper Type', required=True)
    description = fields.Text('Description', required=True)
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Severity', default='medium')
    evidence_photos = fields.One2many('ir.attachment', 'res_id', string='Evidence Photos',
                                      domain=[('res_model', '=', 'utility.tamper.case')])
    evidence_notes = fields.Text('Evidence Notes')
    address = fields.Text('Address')
    reported_by = fields.Many2one('res.users', 'Reported By')
    assigned_to = fields.Many2one('res.users', 'Assigned To')
    estimated_loss = fields.Monetary('Estimated Loss', currency_field='company_currency_id')
    penalty_amount = fields.Monetary('Penalty Amount', currency_field='company_currency_id')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Currency')
    state = fields.Selection([
        ('reported', 'Reported'),
        ('investigating', 'Investigating'),
        ('confirmed', 'Confirmed'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ], string='State', default='reported')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('case_number', _('New')) == _('New'):
                vals['case_number'] = self.env['ir.sequence'].next_by_code('utility.tamper.case') or _('New')
        return super().create(vals_list)
