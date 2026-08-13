import json
import logging

import requests

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

SENSITIVE_PAYLOAD_KEYS = {
    'token', 'callback_token', 'access_token', 'signature', 'authorization',
    'api_key', 'apikey', 'secret', 'password', 'jwt', 'auth_token', 'webhook_secret',
}


def sanitize_sensitive_payload(payload):
    """Sanitize sensitive keys (tokens, secrets, signatures, passwords) in payloads.
    Supports python dicts, JSON strings, or stringified dicts."""
    if not payload:
        return payload

    if isinstance(payload, str):
        try:
            data = json.loads(payload)
            if isinstance(data, dict):
                return json.dumps(sanitize_sensitive_payload(data), ensure_ascii=False)
        except Exception:
            pass
        try:
            import ast
            data = ast.literal_eval(payload)
            if isinstance(data, dict):
                return str(sanitize_sensitive_payload(data))
        except Exception:
            pass
        return payload

    if isinstance(payload, dict):
        clean_dict = {}
        for k, v in payload.items():
            if str(k).lower() in SENSITIVE_PAYLOAD_KEYS:
                clean_dict[k] = '***REDACTED***'
            elif isinstance(v, dict):
                clean_dict[k] = sanitize_sensitive_payload(v)
            elif isinstance(v, list):
                clean_dict[k] = [sanitize_sensitive_payload(item) if isinstance(item, dict) else item for item in v]
            else:
                clean_dict[k] = v
        return clean_dict

    return payload


# أنواع المزودين المدعومة لعمليات الدفع
PAYMENT_PROVIDER_TYPES = {'payment_gateway', 'mobile_money', 'bank_transfer', 'direct_debit'}


class UtilityIntegrationProvider(models.Model):
    _name = 'utility.integration.provider'
    _description = 'مزود تكامل خارجي'
    _order = 'sequence, name'

    name = fields.Char('الاسم', required=True)
    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True, index=True,
        default=lambda self: self.env.company,
    )
    sequence = fields.Integer('الترتيب', default=10)
    active = fields.Boolean('نشط', default=True)
    provider_type = fields.Selection([
        ('sms', 'رسائل قصيرة (SMS)'),
        ('ami', 'قراءة تلقائية (AMI)'),
        ('payment_gateway', 'بوابة دفع إلكتروني'),
        ('mobile_money', 'محفظة إلكترونية / Mobile Money'),
        ('bank_transfer', 'تحويل بنكي'),
        ('direct_debit', 'خصم مباشر (Direct Debit)'),
    ], string='نوع المزود', required=True, index=True)

    # ── اتجاه الدفع المدعوم ────────────────────────────────────────────────
    payment_direction = fields.Selection([
        ('inbound', 'وارد فقط — المشترك يدفع للشركة'),
        ('outbound', 'صادر فقط — الشركة تدفع للمشترك (استرداد/تعويض)'),
        ('both', 'كلا الاتجاهين'),
    ], string='اتجاه الدفع', default='inbound',
        help='يحدد ما إذا كان المزود يدعم تحصيل مدفوعات من المشتركين، '
             'أو إرجاع مبالغ لهم، أو كليهما.',
    )

    # ── وضع التكامل ────────────────────────────────────────────────────────
    mode = fields.Selection([
        ('manual', 'يدوي/تجريبي'),
        ('http_json', 'اتصال HTTP (JSON)'),
    ], string='وضع التكامل', default='manual', required=True)
    endpoint_url = fields.Char('Endpoint URL')
    timeout = fields.Integer('مهلة الانتظار (ثواني)', default=15)

    # ── المصادقة ───────────────────────────────────────────────────────────
    auth_header_style = fields.Selection([
        ('bearer', 'Bearer Token'),
        ('basic', 'Basic Auth (user:pass base64)'),
        ('api_key_header', 'API Key في Header مخصص'),
        ('hmac', 'HMAC Signature'),
        ('none', 'بدون مصادقة'),
    ], string='أسلوب المصادقة', default='bearer')
    api_key = fields.Char('API Key / Token')
    api_key_header_name = fields.Char(
        'اسم Header المفتاح',
        default='X-API-Key',
        help='اسم الـ HTTP header الذي يُرسَل فيه المفتاح (عند اختيار api_key_header).',
    )
    webhook_secret = fields.Char('Webhook Secret')

    # ── headers مخصصة (JSON) ───────────────────────────────────────────────
    extra_headers = fields.Text(
        'Headers إضافية (JSON)',
        help='JSON object يحتوي headers إضافية ترسل مع كل طلب.\n'
             'مثال: {"X-Tenant": "utility-main", "Accept-Language": "ar"}',
    )

    # ── يوميات الدفع المرتبطة ─────────────────────────────────────────────
    inbound_journal_id = fields.Many2one(
        'account.journal', string='يومية التحصيل (وارد)',
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
        help='اليومية المحاسبية التي تُسجَّل فيها المدفوعات الواردة عبر هذا المزود. '
             'إذا تُرك فارغاً، سيستخدم النظام اليومية الافتراضية من الإعدادات.',
    )
    outbound_journal_id = fields.Many2one(
        'account.journal', string='يومية الصرف (صادر)',
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
        help='اليومية المحاسبية التي تُسجَّل فيها المدفوعات الصادرة (الاستردادات) عبر هذا المزود.',
    )

    last_error = fields.Text('آخر خطأ', readonly=True)

    # ── حقل محسوب لتحديد ما إذا كان المزود يدعم الدفع ─────────────────────
    is_payment_capable = fields.Boolean(
        'قادر على الدفع',
        compute='_compute_is_payment_capable',
        store=True,
        help='True إذا كان نوع المزود يدعم عمليات الدفع.',
    )

    @api.depends('provider_type')
    def _compute_is_payment_capable(self):
        for rec in self:
            rec.is_payment_capable = rec.provider_type in PAYMENT_PROVIDER_TYPES

    @api.constrains('extra_headers')
    def _check_extra_headers_json(self):
        for rec in self:
            if rec.extra_headers:
                try:
                    parsed = json.loads(rec.extra_headers)
                    if not isinstance(parsed, dict):
                        raise ValueError
                except (ValueError, TypeError):
                    raise models.ValidationError(
                        _('حقل "Headers إضافية" يجب أن يكون JSON object صحيح.\n'
                          'مثال: {"X-Custom-Header": "value"}')
                    )

    def _build_headers(self):
        """بناء headers HTTP بشكل ديناميكي حسب أسلوب المصادقة."""
        self.ensure_one()
        headers = {'Content-Type': 'application/json'}

        if self.auth_header_style == 'bearer' and self.api_key:
            headers['Authorization'] = 'Bearer %s' % self.api_key
        elif self.auth_header_style == 'basic' and self.api_key:
            headers['Authorization'] = 'Basic %s' % self.api_key
        elif self.auth_header_style == 'api_key_header' and self.api_key:
            header_name = self.api_key_header_name or 'X-API-Key'
            headers[header_name] = self.api_key
        elif self.auth_header_style == 'hmac' and self.api_key:
            # HMAC signature سيُحسب لاحقاً عند بناء الـ payload
            headers['X-HMAC-Key-Id'] = self.api_key[:8] + '...'

        # إضافة headers مخصصة إضافية
        if self.extra_headers:
            try:
                extra = json.loads(self.extra_headers)
                headers.update({k: str(v) for k, v in extra.items()})
            except (ValueError, TypeError):
                pass

        return headers

    def _get_payment_journal(self, direction='inbound', company=None):
        """إرجاع يومية الدفع المناسبة حسب الاتجاه."""
        self.ensure_one()
        company = company or self.company_id
        env = self.with_company(company).env

        if direction == 'inbound':
            journal = self.inbound_journal_id
            if not journal or journal.company_id != company:
                # fallback: يومية التحصيل من الإعدادات
                journal_id = int(
                    env['ir.config_parameter'].sudo().get_param(
                        'utility.collection_journal_id', 0) or 0
                )
                journal = env['account.journal'].sudo().browse(journal_id) if journal_id else False
                if not journal or journal.company_id != company:
                    journal = env['account.journal'].sudo().search([
                        ('type', 'in', ['bank', 'cash']),
                        ('company_id', '=', company.id),
                    ], limit=1)
            return journal

        # outbound
        journal = self.outbound_journal_id
        if not journal or journal.company_id != company:
            journal_id = int(
                env['ir.config_parameter'].sudo().get_param(
                    'utility.collection_journal_id', 0) or 0
            )
            journal = env['account.journal'].sudo().browse(journal_id) if journal_id else False
            if not journal or journal.company_id != company:
                journal = env['account.journal'].sudo().search([
                    ('type', 'in', ['bank', 'cash']),
                    ('company_id', '=', company.id),
                ], limit=1)
        return journal

    def supports_direction(self, direction):
        """هل يدعم المزود هذا الاتجاه من الدفع؟"""
        self.ensure_one()
        return self.payment_direction in (direction, 'both')

    def call_json(self, payload, event_type, record=None):
        self.ensure_one()
        sanitized = sanitize_sensitive_payload(payload)
        log = self.env['utility.integration.log'].sudo().create({
            'provider_id': self.id,
            'event_type': event_type,
            'model_name': record._name if record else False,
            'res_id': record.id if record else False,
            'request_payload': json.dumps(sanitized, ensure_ascii=False, default=str),
            'state': 'pending',
        })
        if self.mode == 'manual':
            log.write({'state': 'success', 'response_payload': '{"mode": "manual"}'})
            return log
        if not self.endpoint_url:
            message = _('لم يتم ضبط رابط Endpoint للمزود %s.') % self.name
            log.write({'state': 'failed', 'error_message': message})
            self.last_error = message
            return log
        try:
            response = requests.post(
                self.endpoint_url,
                data=json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8'),
                headers=self._build_headers(),
                timeout=self.timeout or 15,
            )
            log.write({
                'http_status': response.status_code,
                'response_payload': response.text[:4000],
                'state': 'success' if 200 <= response.status_code < 300 else 'failed',
                'error_message': False if 200 <= response.status_code < 300 else response.text[:1000],
            })
            if not 200 <= response.status_code < 300:
                self.last_error = response.text[:1000]
        except Exception as exc:
            _logger.exception('Utility integration call failed')
            log.write({'state': 'failed', 'error_message': str(exc)})
            self.last_error = str(exc)
        return log


class UtilityIntegrationLog(models.Model):
    _name = 'utility.integration.log'
    _description = 'سجل التكاملات الخارجية'
    _order = 'create_date desc, id desc'

    provider_id = fields.Many2one('utility.integration.provider', string='المزود', required=True, ondelete='restrict')
    company_id = fields.Many2one(
        'res.company', string='الشركة', related='provider_id.company_id',
        store=True, readonly=True, index=True,
    )
    provider_type = fields.Selection(related='provider_id.provider_type', string='نوع المزود', store=True)
    event_type = fields.Char('نوع الحدث', required=True)
    model_name = fields.Char('النموذج')
    res_id = fields.Integer('معرف السجل')
    request_payload = fields.Text('الطلب')
    response_payload = fields.Text('الاستجابة')
    http_status = fields.Integer('حالة HTTP')
    state = fields.Selection([
        ('pending', 'قيد التنفيذ'),
        ('success', 'ناجح'),
        ('failed', 'فشل'),
    ], string='الحالة', default='pending', index=True)
    error_message = fields.Text('رسالة الخطأ')