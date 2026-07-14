import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class UtilityPrepaidIntegrationLog(models.Model):
    _name = 'utility.prepaid.integration.log'
    _description = 'سجل تكامل الدفع المسبق'
    _rec_name = 'reference'
    _order = 'create_date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company, index=True)
    reference = fields.Char('المرجع', required=True, copy=False, index=True, default=lambda self: _('جديد'))
    create_date = fields.Datetime('التاريخ', default=fields.Datetime.now, index=True)

    integration_type = fields.Selection([
        ('sts', 'STS'),
        ('ami', 'AMI'),
        ('mdms', 'MDMS'),
        ('sms', 'SMS'),
        ('portal', 'بوابة'),
        ('api', 'API'),
        ('payment_gateway', 'بوابة دفع'),
        ('other', 'أخرى'),
    ], 'نوع التكامل', required=True, index=True)

    direction = fields.Selection([
        ('outbound', 'صادر'),
        ('inbound', 'وارد'),
    ], 'الاتجاه', required=True)

    endpoint = fields.Char('النقطة الطرفية')
    method = fields.Char('طريقة الطلب')

    request_payload = fields.Text('بيانات الطلب')
    response_payload = fields.Text('بيانات الرد')

    status = fields.Selection([
        ('success', 'ناجح'),
        ('failed', 'فشل'),
        ('pending', 'قيد الانتظار'),
        ('timeout', 'انتهت المهلة'),
    ], 'الحالة', default='pending', index=True)

    error_message = fields.Text('رسالة الخطأ')
    response_time_ms = fields.Float('وقت الاستجابة (مللي ثانية)')

    related_model = fields.Char('النموذج المرتبط')
    related_id = fields.Integer('معرف السجل المرتبط')

    provider_id = fields.Many2one('utility.sts.provider', 'مزود STS', index=True)
    vending_request_id = fields.Many2one('utility.vending.request', 'طلب البيع', index=True)
    ami_event_id = fields.Many2one('utility.prepaid.ami.event', 'حدث AMI', index=True)

    user_id = fields.Many2one('res.users', 'المستخدم', default=lambda self: self.env.user)
    ip_address = fields.Char('عنوان IP')
    user_agent = fields.Char('User Agent')

    notes = fields.Text('ملاحظات')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('جديد')) == _('جديد'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('utility.prepaid.integration.log') or _('جديد')
        return super().create(vals_list)

    @api.model
    def log_integration(self, integration_type, direction, endpoint, request_payload,
                        status='pending', response_payload=None, error_message=None,
                        related_model=None, related_id=None, provider_id=None,
                        vending_request_id=None, response_time_ms=None):
        return self.create({
            'integration_type': integration_type,
            'direction': direction,
            'endpoint': endpoint,
            'request_payload': request_payload,
            'response_payload': response_payload,
            'status': status,
            'error_message': error_message,
            'related_model': related_model,
            'related_id': related_id,
            'provider_id': provider_id,
            'vending_request_id': vending_request_id,
            'response_time_ms': response_time_ms,
        })
