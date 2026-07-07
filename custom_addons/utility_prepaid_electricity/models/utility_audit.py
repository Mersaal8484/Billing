from odoo import fields, models


class UtilityAudit(models.Model):
    _name = 'utility.audit'
    _description = 'Audit Trail'
    _order = 'create_date desc, id desc'
    _log_access = False
    _rec_name = 'action'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)

    model = fields.Char(string='Model', required=True, index=True)
    res_id = fields.Integer(string='Record ID', required=True, index=True)
    action = fields.Char(string='Action', required=True, index=True)
    description = fields.Text(string='Description', required=True)

    old_value = fields.Text(string='Old Value')
    new_value = fields.Text(string='New Value')

    user_id = fields.Many2one('res.users', string='User', required=True, index=True,
                              default=lambda self: self.env.user)
    user_login = fields.Char(string='User Login', related='user_id.login', store=True)
    ip_address = fields.Char(string='IP Address')
    user_agent = fields.Char(string='User Agent')

    log_date = fields.Datetime(string='Log Date', default=fields.Datetime.now, required=True, index=True)

    def auto_log(self, model, res_id, action, description, old_value=None, new_value=None):
        """Automatically create an audit log entry."""
        return self.create({
            'model': model,
            'res_id': res_id,
            'action': action,
            'description': description,
            'old_value': old_value,
            'new_value': new_value,
            'user_id': self.env.user.id,
        })
