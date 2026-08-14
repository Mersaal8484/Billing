import logging
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError, UserError

_logger = logging.getLogger(__name__)


class UtilityContractTemplateCloneWizard(models.TransientModel):
    _name = 'utility.contract.template.clone.wizard'
    _description = 'معالج استنساخ قالب العقد (Contract Template Clone Wizard)'

    source_template_id = fields.Many2one(
        'utility.contract.template',
        string='قالب العقد المصدر',
        required=True,
        ondelete='cascade',
    )
    source_pricing_mode = fields.Selection(
        related='source_template_id.pricing_mode',
        string='نمط تسعير المصدر',
        readonly=True,
    )
    source_version_code = fields.Char(
        related='source_template_id.current_version_id.version_code',
        string='إصدار المصدر الحالي',
        readonly=True,
    )

    new_name = fields.Char(
        string='اسم القالب الجديد',
        required=True,
    )
    new_code = fields.Char(
        string='رمز القالب الجديد',
        required=True,
    )

    # ── خيارات النسخ والاستنساخ (Copy Options) ──────────────────────────────
    copy_pricing = fields.Boolean(
        string='نسخ إعدادات التسعير والأسعار الأساسية',
        default=True,
        help='نسخ نمط التسعير، سعر الكيلوواط، رسم الخدمة، والحد الأدنى والأقصى.',
    )
    copy_contract_lines = fields.Boolean(
        string='نسخ بنود العقد (Contract Lines)',
        default=True,
        help='نسخ كافة بنود العقد المعرفة على القالب مع ربطها بنفس المنتجات والمعادلات.',
    )
    copy_pricing_blocks = fields.Boolean(
        string='نسخ شرائح التسعير (Pricing Blocks)',
        default=True,
        help='نسخ شرائح التسعير التصاعدية أو الشرائح الموحدة للأنماط block و tier.',
    )
    copy_discount_blocks = fields.Boolean(
        string='نسخ شرائح الخصم التدريجية',
        default=True,
        help='نسخ شرائح الخصم التدريجي المدعوم.',
    )
    copy_discount_configuration = fields.Boolean(
        string='نسخ إعدادات الخصم والدعم (Sponsor & Formula)',
        default=True,
        help='نسخ الجهة الداعمة ومعادلة الخصم الديناميكية.',
    )
    copy_local_fees = fields.Boolean(
        string='نسخ الرسوم المحلية (Local Fees)',
        default=True,
        help='نسخ رسوم المعلم، النظافة، والمجالس المحلية.',
    )
    copy_scope = fields.Boolean(
        string='نسخ نطاق التغطية الجغرافية',
        default=True,
        help='نسخ وتحديد النطاق الجغرافي والمناطق المسموح بها.',
    )
    copy_workflow_settings = fields.Boolean(
        string='نسخ إعدادات سير العمل والفوترة',
        default=True,
        help='نسخ إعدادات التأكيد الآلي، إنشاء الفواتير، وقواعد التكرار.',
    )

    # ── التجاوز الجغرافي (Geographic Override) ──────────────────────────────
    target_scope = fields.Selection([
        ('global', 'عام على جميع المناطق'),
        ('restricted', 'مخصص لمناطق محددة')
    ], string='النطاق الجغرافي المستهدف', default='global', required=True)

    target_region_ids = fields.Many2many(
        'utility.region',
        'utility_clone_wizard_region_rel',
        'wizard_id',
        'region_id',
        string='المناطق الرئيسية المستهدفة',
        domain="[('type', '=', 'region')]",
        help="المناطق الرئيسية المسموح بها للقالب الجديد"
    )
    target_area_ids = fields.Many2many(
        'utility.region',
        'utility_clone_wizard_area_rel',
        'wizard_id',
        'region_id',
        string='المناطق الفرعية/الفروع المستهدفة',
        domain="[('type', '=', 'area')]",
        help="المناطق الفرعية/الفروع المسموح بها للقالب الجديد"
    )

    @api.onchange('source_template_id')
    def _onchange_source_template_id(self):
        if self.source_template_id:
            src = self.source_template_id
            self.new_name = _("%s (نسخة)") % src.name
            self.new_code = f"{src.code or 'CT'}_COPY"
            self.target_scope = src.scope or 'global'
            self.target_region_ids = [(6, 0, src.region_ids.ids)]
            self.target_area_ids = [(6, 0, src.area_ids.ids)]

    def action_clone_template(self):
        """تنفيذ استنساخ قالب العقد بشكل مستقل وذري مع التحقق الصارم من الصلاحيات والقيود."""
        self.ensure_one()

        # 1. التحقق من الصلاحيات الأمنية (Server-Side Group Enforcement)
        is_admin = self.env.user.has_group('utility_core.group_utility_admin') or self.env.is_superuser()
        is_manager = self.env.user.has_group('utility_core.group_utility_billing_manager')
        if not (is_admin or is_manager):
            raise AccessError(_(
                "عفواً، لا تملك الصلاحية لاستنساخ وإنشاء قوالب العقود. "
                "هذه العملية مخصصة لمدراء الفوترة والنظام فقط."
            ))

        source = self.source_template_id
        if not source:
            raise UserError(_("يجب تحديد قالب العقد المصدر للاستنساخ."))

        new_name = (self.new_name or '').strip()
        new_code = (self.new_code or '').strip()

        if not new_name:
            raise ValidationError(_("يجب إدخال اسم للقالب الجديد."))
        if not new_code:
            raise ValidationError(_("يجب إدخال رمز فريد للقالب الجديد."))

        # التحقق من فرادة الرمز
        existing_count = self.env['utility.contract.template'].search_count([
            ('code', '=', new_code),
            ('company_id', '=', source.company_id.id),
        ])
        if existing_count > 0:
            raise ValidationError(_(
                "رمز قالب العقد '%s' مستخدم مسبقاً في شركة '%s'. يرجى اختيار رمز فريد."
            ) % (new_code, source.company_id.name))

        # 2. بناء بيانات القالب الجديد
        template_vals = {
            'name': new_name,
            'code': new_code,
            'company_id': source.company_id.id,
            'currency_id': source.currency_id.id,
            'active': True,
            'cloned_from_template_id': source.id,
            'cloned_at': fields.Datetime.now(),
            'cloned_by': self.env.user.id,
            'recurring_rule_type': source.recurring_rule_type,
            'recurring_invoicing_type': source.recurring_invoicing_type,
            'recurring_interval': source.recurring_interval,
            'pricelist_id': source.pricelist_id.id if source.pricelist_id else False,
            'journal_id': source.journal_id.id if source.journal_id else False,
        }

        # فئات وأنواع المشتركين (إلزامية في القالب وتُنسخ دائماً من المصدر لضمان التوافق التجاري)
        template_vals['subscriber_category_ids'] = [(6, 0, source.subscriber_category_ids.ids)]
        template_vals['subscriber_ids'] = [(6, 0, source.subscriber_ids.ids)]

        # النطاق الجغرافي
        if self.copy_scope:
            template_vals['scope'] = self.target_scope
            if self.target_scope == 'restricted':
                template_vals['region_ids'] = [(6, 0, self.target_region_ids.ids)]
                template_vals['area_ids'] = [(6, 0, self.target_area_ids.ids)]
            else:
                template_vals['region_ids'] = [(5, 0, 0)]
                template_vals['area_ids'] = [(5, 0, 0)]
        else:
            # القالب الجديد يبدأ بنطاق عام دون قيود جغرافية
            template_vals['scope'] = 'global'
            template_vals['region_ids'] = [(5, 0, 0)]
            template_vals['area_ids'] = [(5, 0, 0)]

        # التسعير
        if self.copy_pricing:
            template_vals['pricing_mode'] = source.pricing_mode
            template_vals['price_per_kwh'] = source.price_per_kwh
            template_vals['service_charge'] = source.service_charge
            template_vals['min_charge'] = source.min_charge
            template_vals['max_charge'] = source.max_charge
            template_vals['effective_date'] = source.effective_date
            template_vals['end_date'] = source.end_date
        else:
            template_vals['pricing_mode'] = 'flat'
            template_vals['price_per_kwh'] = 0.0
            template_vals['service_charge'] = 0.0

        # الرسوم المحلية
        if self.copy_local_fees:
            template_vals['local_fee_per_kwh'] = source.local_fee_per_kwh
            template_vals['local_fee_mu_allim'] = source.local_fee_mu_allim
            template_vals['local_fee_cleaning'] = source.local_fee_cleaning

        # خصم الدعم والمعادلات
        if self.copy_discount_configuration:
            template_vals['sponsor_id'] = source.sponsor_id.id if source.sponsor_id else False
            template_vals['discount_formula_id'] = source.discount_formula_id.id if source.discount_formula_id else False

        # سير العمل
        if self.copy_workflow_settings:
            template_vals['sale_autoconfirm'] = source.sale_autoconfirm
            template_vals['create_invoice_automatically'] = source.create_invoice_automatically
            template_vals['validate_invoice_automatically'] = source.validate_invoice_automatically
            template_vals['is_auto_pay'] = source.is_auto_pay
            template_vals['auto_pay_retries'] = source.auto_pay_retries
            template_vals['auto_pay_retry_hours'] = source.auto_pay_retry_hours

        # 3. بناء وتجهيز أسطر التكوينات التابعة المستقلة (Independent Child Records)
        # بنود العقد
        if self.copy_contract_lines and source.line_ids:
            line_commands = []
            for l in source.line_ids.sorted('sequence'):
                line_commands.append((0, 0, {
                    'sequence': l.sequence,
                    'product_id': l.product_id.id,
                    'name': l.name,
                    'quantity': l.quantity,
                    'uom_id': l.uom_id.id if l.uom_id else False,
                    'price_type': l.price_type,
                    'specific_price': l.specific_price,
                    'meter_line_type': l.meter_line_type,
                    'qty_formula_id': l.qty_formula_id.id if l.qty_formula_id else False,
                    'is_subsidized': l.is_subsidized,
                }))
            template_vals['line_ids'] = line_commands

        # شرائح التسعير
        if self.copy_pricing_blocks and source.block_ids:
            block_commands = []
            for b in source.block_ids.sorted(lambda x: (x.from_kwh, x.sequence, x.id)):
                block_commands.append((0, 0, {
                    'sequence': b.sequence,
                    'name': b.name,
                    'from_kwh': b.from_kwh,
                    'to_kwh': b.to_kwh,
                    'price_per_kwh': b.price_per_kwh,
                    'from_month': b.from_month,
                    'to_month': b.to_month,
                    'time_from': b.time_from,
                    'time_to': b.time_to,
                    'is_discount': False,
                }))
            template_vals['block_ids'] = block_commands

        # شرائح الخصم التدريجي
        if self.copy_discount_blocks and source.discount_block_ids:
            discount_block_commands = []
            for db in source.discount_block_ids.sorted(lambda x: (x.from_kwh, x.sequence, x.id)):
                discount_block_commands.append((0, 0, {
                    'sequence': db.sequence,
                    'name': db.name,
                    'from_kwh': db.from_kwh,
                    'to_kwh': db.to_kwh,
                    'price_per_kwh': db.price_per_kwh,
                    'from_month': db.from_month,
                    'to_month': db.to_month,
                    'time_from': db.time_from,
                    'time_to': db.time_to,
                    'is_discount': True,
                }))
            template_vals['discount_block_ids'] = discount_block_commands

        # 4. الإنشاء الذري والتحقق الكامل
        new_template = self.env['utility.contract.template'].create(template_vals)

        # 5. فتح نموذج القالب المستنسخ الجديد
        return {
            'type': 'ir.actions.act_window',
            'name': _('قالب العقد المستنسخ: %s') % new_template.name,
            'res_model': 'utility.contract.template',
            'res_id': new_template.id,
            'view_mode': 'form',
            'target': 'current',
        }
