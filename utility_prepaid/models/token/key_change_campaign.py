import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UtilityKeyChangeCampaign(models.Model):
    _name = 'utility.key.change.campaign'
    _description = 'حملة تغيير مفتاح STS'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company, index=True)
    name = fields.Char('اسم الحملة', required=True)
    reference = fields.Char('المرجع', copy=False, index=True, default=lambda self: _('جديد'))

    description = fields.Text('الوصف')
    date_start = fields.Date('تاريخ البداية')
    date_end = fields.Date('تاريخ النهاية')

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('planned', 'مُخطط'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغى'),
    ], 'الحالة', default='draft', tracking=True)

    provider_id = fields.Many2one('utility.sts.provider', 'مزود STS', required=True, index=True)
    meter_ids = fields.Many2many('utility.meter', 'utility_key_change_campaign_meter_rel', string='العدادات المستهدفة')
    meter_count = fields.Integer('عدد العدادات', compute='_compute_meter_count', store=True)

    total_tokens_generated = fields.Integer('إجمالي التوكنات المولدة', default=0)
    total_tokens_failed = fields.Integer('إجمالي التوكنات الفاشلة', default=0)
    total_tokens_pending = fields.Integer('إجمالي التوكنات المعلقة', default=0)

    key_revision_from = fields.Char('مراجعة المفتاح من')
    key_revision_to = fields.Char('مراجعة المفتاح إلى')

    notes = fields.Text('ملاحظات')
    operator_id = fields.Many2one('res.users', 'المشغل', default=lambda self: self.env.user)

    token_ids = fields.One2many('utility.token', 'key_change_campaign_id', 'توكنات تغيير المفتاح')

    @api.depends('meter_ids')
    def _compute_meter_count(self):
        for rec in self:
            rec.meter_count = len(rec.meter_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('جديد')) == _('جديد'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('utility.key.change.campaign') or _('جديد')
        return super().create(vals_list)

    def action_start(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('يمكن بدء الحملة فقط من حالة المسودة.'))
            rec.state = 'planned'

    def action_launch(self):
        for rec in self:
            if rec.state != 'planned':
                raise UserError(_('يجب تخطيط الحملة قبل تنفيذها.'))
            rec.state = 'in_progress'
            rec._generate_key_change_tokens()

    def action_complete(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_('يمكن إكمال الحملة فقط أثناء التنفيذ.'))
            rec.state = 'completed'

    def action_cancel(self):
        for rec in self:
            if rec.state in ('completed',):
                raise UserError(_('لا يمكن إلغاء حملة مكتملة.'))
            rec.state = 'cancelled'

    def _generate_key_change_tokens(self):
        self.ensure_one()
        for meter in self.meter_ids:
            try:
                result = self.provider_id.send_generate_token(
                    meter_number=meter.meter_number,
                    amount=0,
                    kwh=0,
                    token_type='key_change',
                    extra={
                        'key_revision_from': self.key_revision_from,
                        'key_revision_to': self.key_revision_to,
                    },
                )
                token_vals = {
                    'company_id': self.company_id.id,
                    'meter_id': meter.id,
                    'account_id': meter.customer_id.id if meter.customer_id else False,
                    'customer_id': meter.customer_id.partner_id.id if meter.customer_id and meter.customer_id.partner_id else False,
                    'token_type': 'key_change',
                    'key_change_campaign_id': self.id,
                    'sts_server': self.provider_id.name,
                }
                if result.get('success'):
                    token_vals.update({
                        'token_number': result.get('token_value'),
                        'token_identifier': result.get('token_identifier'),
                        'status': 'success',
                        'provider_reference': result.get('provider_reference'),
                        'response_date': fields.Datetime.now(),
                    })
                    self.total_tokens_generated += 1
                else:
                    token_vals.update({
                        'status': 'failed',
                        'response_code': result.get('error_code', 'ERROR'),
                        'response_message': result.get('error_message', ''),
                    })
                    self.total_tokens_failed += 1
                self.env['utility.token'].create(token_vals)
            except Exception as e:
                _logger.exception('Key change token failed for meter %s', meter.meter_number)
                self.total_tokens_failed += 1

    def action_view_tokens(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('توكنات تغيير المفتاح'),
            'res_model': 'utility.token',
            'domain': [('key_change_campaign_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }
