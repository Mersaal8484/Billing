from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import re

PHONE_9_RE = re.compile(r'^\d{9}$')


class SaleOrderType(models.Model):
    _name = 'sale.order.type'
    _description = 'نوع أمر البيع'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)

    description = fields.Text(string='Description', translate=True)
    sequence_id = fields.Many2one('ir.sequence', string='Entry Sequence', copy=False)
    journal_id = fields.Many2one('account.journal', string='Billing Journal', domain="[('type', '=', 'sale')]")
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    picking_policy = fields.Selection([
        ('direct', 'Deliver each product when available'),
        ('one', 'Deliver all products at once'),
    ], string='Shipping Policy', default='direct')
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term')
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    incoterm_id = fields.Many2one('account.incoterms', string='Incoterm')
    sequence = fields.Integer(default=10)
    rule_ids = fields.One2many('sale.order.type.rule', 'order_type_id', string='Rules', copy=True)

    def matches_order(self, order):
        self.ensure_one()
        return any(rule.matches_order(order) for rule in self.rule_ids)

    def matches_invoice(self, invoice):
        self.ensure_one()
        return any(rule.matches_invoice(invoice) for rule in self.rule_ids)


class SaleOrderTypeRule(models.Model):
    _name = 'sale.order.type.rule'
    _description = 'قاعدة المطابقة التلقائية لنوع أمر البيع'
    _order = 'sequence'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    order_type_id = fields.Many2one('sale.order.type', string='Order Type', ondelete='cascade')
    product_ids = fields.Many2many('product.product', string='Products')
    product_category_ids = fields.Many2many('product.category', string='Product Categories')

    def matches_order(self, order):
        self.ensure_one()
        order_products = order.order_line.mapped('product_id')
        return self.matches_products(order_products) or self.matches_product_categories(order_products.mapped('categ_id'))

    def matches_products(self, products):
        self.ensure_one()
        return self.product_ids and any(p in products for p in self.product_ids)

    def matches_product_categories(self, categories):
        self.ensure_one()
        return self.product_category_ids and any(c in categories for c in self.product_category_ids)

    def matches_invoice(self, invoice):
        self.ensure_one()
        invoice_products = invoice.invoice_line_ids.mapped('product_id')
        return self.matches_products(invoice_products) or self.matches_product_categories(invoice_products.mapped('categ_id'))


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_contract = fields.Boolean(string='هل هو عقد اشتراك')
    contract_template_id = fields.Many2one(
        'utility.contract.template',
        string='قالب عقد الكهرباء',
    )

    @api.onchange('is_contract')
    def _change_is_contract(self):
        if not self.is_contract:
            self.contract_template_id = False


class ResPartnerSector(models.Model):
    _name = 'res.partner.sector'
    _description = 'قطاع المشترك'

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code")
    active = fields.Boolean(string="Active", default=True)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    region_id = fields.Many2one('utility.region', string='المنطقة', domain="[('type', '=', 'region')]")
    area_id = fields.Many2one('utility.region', string='المنطقة الفرعية', domain="[('type', '=', 'area')]")
    zone_id = fields.Many2one('utility.region', string='المنطقة التفصيلية', domain="[('type', '=', 'zone')]")

    nickname = fields.Char(string="الاسم المختصر")
    is_subscriber = fields.Boolean(string="مشترك كهرباء (Is Subscriber)", default=False, tracking=True)
    last_payment = fields.Monetary(string="آخر دفعة", compute='_compute_last_payment', store=False)
    last_payment_date = fields.Date(string="تاريخ آخر دفعة", compute='_compute_last_payment', store=False)
    last_invoice = fields.Monetary(string="آخر فاتورة", compute='_compute_last_invoice', store=False)
    last_invoice_date = fields.Date(string="تاريخ آخر فاتورة", compute='_compute_last_invoice', store=False)
    char_code = fields.Char(string="الحرف")
    old_payment = fields.Monetary(string="آخر دفعة من المؤسسة")
    old_credit = fields.Monetary(string="الرصيد السابق من المؤسسة")
    new_no = fields.Char(string="الرقم الجديد")
    opening_reading = fields.Integer(string="قراءة الافتتاح")
    register_number = fields.Integer(string="رقم السجل")
    is_credit_raised = fields.Boolean(string="رصيد مرحل")
    n11 = fields.Integer(string="N11")
    pec_credit = fields.Monetary(string="رصيد مرحل من المؤسسة")
    credit_raise_date = fields.Date(string="تاريخ الترحيل")
    reading_multiplier = fields.Float(string="معامل القراءة")
    tariff_code = fields.Char(string="رمز التعرفة من المؤسسة")
    subscription_amount_partner = fields.Integer(string="قيمة الاشتراك في المؤسسة")
    opening_journal_no = fields.Integer(string="رقم يومية رصيد الافتتاح")
    vas = fields.Integer(string="VAS")
    meter_digit_count = fields.Integer(string="عدد أرقام العداد")
    base_name = fields.Char(string="الاسم الأساسي من المؤسسة")
    old_credit_before = fields.Monetary(string="الرصيد السابق قبل الحساب")
    n1 = fields.Integer(string="N1")
    n2 = fields.Integer(string="N2")
    n3 = fields.Integer(string="N3")
    balance_customer = fields.Monetary(string="إجمالي مدين المشترك", readonly=True)
    credit_last = fields.Monetary(string="آخر رصيد")

    sale_type = fields.Many2one('sale.order.type', string='نوع أمر البيع', company_dependent=True)
    subscriber_id = fields.Many2one('utility.subscriber', string="نوع المشترك", tracking=True)
    sector_id = fields.Many2one('res.partner.sector', string="القطاع (Sector)", tracking=True)

    utility_region_id = fields.Many2one('utility.region', string="المنطقة التشغيلية (Region)", domain="[('type', '=', 'region')]")
    utility_area_id = fields.Many2one('utility.region', string="الفرع التشغيلي (Area)", domain="[('type', '=', 'area')]")
    direct_branch_id = fields.Many2one('utility.region', string="فرع الخدمة المباشر (Direct Branch)", domain="[('type', '=', 'area')]")
    transformer_zone_id = fields.Many2one('utility.region', string="نطاق المحول (Transformer Zone)", domain="[('type', '=', 'zone')]")
    residential_compound_id = fields.Many2one('utility.region', string="الحي أو المجمع السكني (Compound)", domain="[('type', '=', 'zone')]")
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account', 
        string="الحساب التحليلي",
        compute="_compute_analytic_account_id", 
        store=False
    )

    def _compute_analytic_account_id(self):
        for partner in self:
            account = self.env['account.analytic.account'].search([('partner_id', '=', partner.id)], limit=1)
            partner.analytic_account_id = account.id if account else False

    payment_token_id = fields.Many2one(
        'payment.token',
        string='رمز الدفع',
        domain="[('id', 'in', payment_token_ids)]",
    )

    def _compute_last_payment(self):
        for partner in self:
            partner.last_payment = 0.0
            partner.last_payment_date = False
            if not partner.id:
                continue
            payment = self.env['account.payment'].search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'posted')
            ], order='date desc', limit=1)
            if payment:
                partner.last_payment = payment.amount
                partner.last_payment_date = payment.date

    def _compute_last_invoice(self):
        for partner in self:
            partner.last_invoice = 0.0
            partner.last_invoice_date = False
            if not partner.id:
                continue
            invoice = self.env['account.move'].search([
                ('partner_id', '=', partner.id),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted')
            ], order='invoice_date desc', limit=1)
            if invoice:
                partner.last_invoice = invoice.amount_total
                partner.last_invoice_date = invoice.invoice_date

    def _compute_display_name(self):
        super()._compute_display_name()
        if self._context.get('show_nickname'):
            for partner in self:
                if partner.nickname:
                    partner.display_name = f"[{partner.nickname}] {partner.name}"

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        domain = domain or []
        if name:
            domain = ['|', ('name', operator, name), ('nickname', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)

    def _get_partner_balance(self, date_cutoff=None, date_range_id=None, journal_type=None, exclude_journal_type=None, date_range_not_null=False, date_range_is_null=False):
        self.ensure_one()
        query = """SELECT sum(l.debit - l.credit) as opening_bal
                   FROM account_move_line l
                   JOIN account_account a ON l.account_id = a.id"""
        if journal_type or exclude_journal_type:
            query += " JOIN account_journal j ON l.journal_id = j.id"
            
        query += " WHERE l.partner_id = %s AND a.account_type = 'asset_receivable'"
        params = [self.id]
        
        if date_cutoff:
            query += " AND l.date < %s"
            params.append(date_cutoff)
        if date_range_id:
            query += " AND l.date_range_id = %s"
            params.append(date_range_id)
        if journal_type:
            query += " AND j.type = %s"
            params.append(journal_type)
        if exclude_journal_type:
            query += " AND j.type != %s"
            params.append(exclude_journal_type)
        if date_range_not_null:
            query += " AND l.date_range_id IS NOT NULL"
        if date_range_is_null:
            query += " AND l.date_range_id IS NULL"
            
        self.env.cr.execute(query, params)
        res = self.env.cr.fetchone()
        return res[0] or 0.0

    @api.constrains('phone', 'mobile')
    def _check_phone_9_digits(self):
        for partner in self:
            if partner.phone and not PHONE_9_RE.match(partner.phone):
                raise ValidationError(
                    'رقم الهاتف يجب أن يتكون من 9 أرقام فقط، بدون مفتاح دولة (+967/00) أو شرطات.'
                )
            if partner.mobile and not PHONE_9_RE.match(partner.mobile):
                raise ValidationError(
                    'رقم الجوال يجب أن يتكون من 9 أرقام فقط، بدون مفتاح دولة (+967/00) أو شرطات.'
                )
