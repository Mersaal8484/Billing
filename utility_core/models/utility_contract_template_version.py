import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityContractTemplateVersion(models.Model):
    _name = 'utility.contract.template.version'
    _description = 'إصدار قالب عقد الكهرباء (Contract Template Commercial Version)'
    _order = 'template_id, version_number desc, id desc'
    _rec_name = 'display_name'

    template_id = fields.Many2one(
        'utility.contract.template',
        string='قالب العقد',
        required=True,
        index=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company',
        related='template_id.company_id',
        string='الشركة',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='template_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )
    version_number = fields.Integer(
        string='رقم الإصدار',
        required=True,
        default=1,
        index=True,
    )
    version_code = fields.Char(
        string='رمز الإصدار',
        required=True,
        index=True,
    )
    display_name = fields.Char(
        string='اسم العرض',
        compute='_compute_display_name',
        store=True,
    )
    created_at = fields.Datetime(
        string='تاريخ الإنشاء',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    created_by = fields.Many2one(
        'res.users',
        string='أنشئ بواسطة',
        default=lambda self: self.env.user,
        readonly=True,
    )

    # ── البيانات التجارية المسعرة ──────────────────────────────────────────
    pricing_mode = fields.Selection([
        ('flat', 'سعر موحّد بدون شرائح'),
        ('tier', 'Flat Tier / سعر شريحة واحدة'),
        ('block', 'Progressive Tier / شرائح تصاعدية'),
        ('seasonal', 'موسمي'),
        ('tou', 'حسب وقت الاستخدام'),
    ], string='نمط التسعير', required=True, default='flat')

    price_per_kwh = fields.Monetary(
        string='سعر الكيلوواط/ساعة',
        default=0.0,
        currency_field='currency_id',
    )
    service_charge = fields.Monetary(
        string='رسم الخدمة الثابت',
        default=0.0,
        currency_field='currency_id',
    )
    min_charge = fields.Monetary(
        string='الحد الأدنى للفوترة',
        default=0.0,
        currency_field='currency_id',
    )
    max_charge = fields.Monetary(
        string='الحد الأقصى للفوترة',
        default=0.0,
        currency_field='currency_id',
    )

    # الرسوم المحلية
    local_fee_per_kwh = fields.Monetary(
        string='رسم محلي لكل kWh',
        default=0.0,
        currency_field='currency_id',
    )
    local_fee_mu_allim = fields.Monetary(
        string='رسم المعلم لكل kWh',
        default=0.0,
        currency_field='currency_id',
    )
    local_fee_cleaning = fields.Monetary(
        string='رسم النظافة لكل kWh',
        default=0.0,
        currency_field='currency_id',
    )

    # الدعم والخصم
    sponsor_id = fields.Many2one(
        'res.partner',
        string='الجهة الداعمة',
    )
    discount_formula_id = fields.Many2one(
        'utility.formula',
        string='معادلة الخصم',
    )
    discount_formula_name = fields.Char(
        string='اسم معادلة الخصم',
    )

    # لقطة JSON شاملة للبيانات والبنود والشرائح
    pricing_snapshot_json = fields.Text(
        string='لقطة التكوين الكاملة (JSON)',
        help='لقطة مسلسلة لكافة تفاصيل الهيدر، البنود، الشرائح والمعادلات المعتمدة في هذا الإصدار',
    )

    is_used_in_billing = fields.Boolean(
        string='مستخدم في فواتير',
        compute='_compute_is_used_in_billing',
        store=True,
        help='يشير إلى ما إذا كان هذا الإصدار قد استُخدم في إنشاء فواتير سابقة ومقفل ضد التعديل',
    )

    _sql_constraints = [
        ('unique_template_version', 'unique(template_id, version_number)',
         'رقم الإصدار يجب أن يكون فريداً لقالب العقد الواحد.'),
    ]

    @api.depends('template_id.name', 'version_number', 'version_code')
    def _compute_display_name(self):
        for rec in self:
            t_name = rec.template_id.name or _('قالب غير محدد')
            rec.display_name = f"{t_name} (v{rec.version_number})"

    def _compute_is_used_in_billing(self):
        # البحث في sale.order إذا كان هذا الإصدار مستخدماً في فواتير نشطة
        if 'sale.order' in self.env:
            for rec in self:
                count = self.env['sale.order'].sudo().search_count([
                    ('contract_template_version_id', '=', rec.id),
                ])
                rec.is_used_in_billing = bool(count > 0)
        else:
            for rec in self:
                rec.is_used_in_billing = False

    def write(self, vals):
        """حماية الإصدارات المستخدمة من التعديل الصامت."""
        if not self.env.context.get('_force_version_update'):
            for rec in self:
                if rec.is_used_in_billing:
                    raise UserError(_(
                        "لا يمكن تعديل إصدار قالب العقد (%s) لأنه مستخدم في فواتير كهرباء سابقة. "
                        "التعديلات على القالب يجب أن تنشئ إصداراً جديداً للحفاظ على سلامة التدقيق المالي."
                    ) % rec.display_name)
        return super().write(vals)

    def unlink(self):
        """حماية الإصدارات المستخدمة من الحذف."""
        if not self.env.context.get('_force_version_unlink'):
            for rec in self:
                if rec.is_used_in_billing:
                    raise UserError(_(
                        "لا يمكن حذف إصدار قالب العقد (%s) لأنه مستخدم كمرجع مالي لفواتير سابقة."
                    ) % rec.display_name)
        return super().unlink()

    def get_parsed_snapshot(self):
        """إرجاع لقطة التكوين كـ Dictionary بايثون."""
        self.ensure_one()
        if not self.pricing_snapshot_json:
            return {}
        try:
            return json.loads(self.pricing_snapshot_json)
        except Exception as e:
            _logger.error("Failed to parse pricing snapshot JSON for version %s: %s", self.id, e)
            return {}
