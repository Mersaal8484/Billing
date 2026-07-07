from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    session_ids = fields.One2many(
        'session.manager',
        'user_id',
        string='Sessions'
    )

    active_session_count = fields.Integer(
        string='Active Sessions',
        compute='_compute_active_session_count',
        store=False
    )
    restrict_ip = fields.Boolean(string='Restrict by IP')
    allowed_ips = fields.Text(
        string='Allowed IPs',
        help="Comma-separated list of allowed IP addresses"
    )
    max_sessions = fields.Integer(
        string='Maximum Concurrent Sessions',
        default=3
    )
    session_duration = fields.Integer(
        string='Custom Session Duration (hours)',
        help="Leave empty to use system default"
    )
    session_control_enabled = fields.Boolean(string='Enable Session Control', default=True)
    notify_on_new_session = fields.Boolean(string='Notify on New Login')
    last_session_id = fields.Many2one('session.manager', string='Last Session')
    policy_ids = fields.Many2many('session.policy', string='Session Policies')

    # Enhanced session count computation
    @api.depends('session_ids.is_active')
    def _compute_active_session_count(self):
        session_data = self.env['session.manager'].read_group(
            [('user_id', 'in', self.ids), ('is_active', '=', True)],
            ['user_id'],
            ['user_id']
        )
        mapped_data = {data['user_id'][0]: data['user_id_count'] for data in session_data}
        for user in self:
            user.active_session_count = mapped_data.get(user.id, 0)

    # New method to check and enforce session limits
    def check_sessions(self):
        """Check and enforce session limits based on policies"""
        for user in self:
            if not user.session_control_enabled:
                continue

            # Get the most restrictive policy
            max_sessions = user.max_sessions
            for policy in user.policy_ids:
                if policy.max_sessions and policy.max_sessions < max_sessions:
                    max_sessions = policy.max_sessions

            if user.active_session_count > max_sessions:
                oldest_active = user.session_ids.filtered(
                    lambda s: s.is_active
                ).sorted('last_access')[:1]
                oldest_active.force_logout()

    # Enhanced session view with more options
    def action_view_sessions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - Sessions',
            'res_model': 'session.manager',
            'view_mode': 'tree,form,graph,pivot',
            'domain': [('user_id', '=', self.id)],
            'context': {
                'default_user_id': self.id,
                'search_default_active': 1,
                'graph_measure': 'create_date',
                'graph_groupbys': ['device_type']
            },
            'views': [
                (False, 'tree'),
                (False, 'form'),
                (False, 'graph'),
                (False, 'pivot')
            ]
        }

    # New method to apply policies
    def apply_session_policies(self):
        """Apply all session policies to user's active sessions"""
        for user in self:
            for session in user.session_ids.filtered(lambda s: s.is_active):
                policy = session.policy_id or self.env['session.policy'].search([
                    ('active', '=', True),
                    ('user_ids', 'in', user.id)
                ], limit=1)

                if policy:
                    session.write({
                        'policy_id': policy.id
                    })
                    if policy.apply_expiry and policy.session_duration:
                        session.extend_session(policy.session_duration)

    @api.depends('session_ids.is_active')
    def _compute_active_session_count(self):
        for user in self:
            user.active_session_count = len(user.session_ids.filtered(lambda s: s.is_active))

    def action_view_sessions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'User Sessions',
            'res_model': 'session.manager',
            'view_mode': 'tree,form',
            'domain': [('user_id', '=', self.id)],
            'context': {'default_user_id': self.id},
        }