from contextlib import contextmanager
import logging
from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


@contextmanager
def savepoint(cr):
    try:
        with cr.savepoint():
            yield
    except Exception:
        _logger.exception('Automatic Workflow Job failed (savepoint)')



def _resolve_domain(domain):
    if isinstance(domain, str):
        return safe_eval(domain or '[]')
    return domain or []


class SaleWorkflowProcess(models.Model):
    _name = 'sale.workflow.process'
    _description = 'عملية سير أمر البيع'

    name = fields.Char(required=True, string="اسم مسار العمل")
    picking_policy = fields.Selection([
        ('direct', 'تسليم كل منتج عند توفره (Direct)'),
        ('one', 'تسليم كل المنتجات دفعة واحدة (All at once)'),
    ], default='direct', string="سياسة التسليم")
    validate_order = fields.Boolean(string='تأكيد أمر البيع تلقائياً')
    order_filter_domain = fields.Text(related='order_filter_id.domain', readonly=False, string="فلتر أوامر البيع")
    create_invoice = fields.Boolean(string='إنشاء الفاتورة تلقائياً')
    create_invoice_filter_domain = fields.Text(related='create_invoice_filter_id.domain', readonly=False, string="نطاق فلتر إنشاء الفواتير")
    validate_invoice = fields.Boolean(string='ترحيل الفاتورة تلقائياً')
    validate_invoice_filter_domain = fields.Text(related='validate_invoice_filter_id.domain', readonly=False, string="نطاق فلتر ترحيل الفواتير")
    validate_picking = fields.Boolean(string='تأكيد وتسليم المخزون تلقائياً')
    picking_filter_domain = fields.Text(related='picking_filter_id.domain', readonly=False, string="فلتر حركات المخزون")
    invoice_date_is_order_date = fields.Boolean(string='فرض تاريخ أمر البيع كـتاريخ للفاتورة')
    invoice_service_delivery = fields.Boolean(string='فوترة الخدمة عند التسليم')
    sale_done = fields.Boolean(string='إغلاق أمر البيع تلقائياً')
    sale_done_filter_domain = fields.Text(related='sale_done_filter_id.domain', readonly=False, string="فلتر إغلاق المبيعات")
    warning = fields.Text(string='رسالة تحذيرية', translate=True)
    team_id = fields.Many2one('crm.team', string='فريق المبيعات')
    property_journal_id = fields.Many2one('account.journal', company_dependent=True, string='يومية المبيعات')
    order_filter_id = fields.Many2one('ir.filters', string='فلتر الطلبات', domain="[('model_id', '=', 'sale.order')]")
    picking_filter_id = fields.Many2one('ir.filters', string='فلتر الشحنات', domain="[('model_id', '=', 'stock.picking')]")
    create_invoice_filter_id = fields.Many2one('ir.filters', string='فلتر إنشاء الفواتير', domain="[('model_id', '=', 'sale.order')]")
    validate_invoice_filter_id = fields.Many2one('ir.filters', string='فلتر ترحيل الفواتير', domain="[('model_id', '=', 'account.move')]")
    sale_done_filter_id = fields.Many2one('ir.filters', string='فلتر إغلاق الطلبات', domain="[('model_id', '=', 'sale.order')]")


class AutomaticWorkflowJob(models.Model):
    _name = 'automatic.workflow.job'
    _description = 'وظيفة سير تلقائي'

    @api.model
    def _validate_sale_orders(self, order_filter):
        orders = self.env['sale.order'].search(order_filter)
        for order in orders:
            with savepoint(self.env.cr):
                order.action_confirm()

    @api.model
    def _create_invoices(self, create_filter):
        sale_orders = self.env['sale.order'].search(create_filter)
        for order in sale_orders:
            with savepoint(self.env.cr):
                context = {'active_model': 'sale.order', 'active_ids': [order.id], 'active_id': order.id}
                wizard = self.env['sale.advance.payment'].with_context(context).create({})
                wizard.create_invoices()

    @api.model
    def _validate_invoices(self, validate_invoice_filter):
        moves = self.env['account.move'].search(validate_invoice_filter)
        for move in moves:
            if not move.invoice_line_ids:
                continue
            with savepoint(self.env.cr):
                move.action_post()

    @api.model
    def _validate_pickings(self, picking_filter):
        pickings = self.env['stock.picking'].search(picking_filter)
        for picking in pickings:
            with savepoint(self.env.cr):
                picking.validate_picking()

    @api.model
    def _sale_done(self, sale_done_filter):
        orders = self.env['sale.order'].search(sale_done_filter)
        for order in orders:
            with savepoint(self.env.cr):
                order.action_done()

    @api.model
    def run_with_workflow(self, sale_workflow):
        if sale_workflow.validate_order:
            domain = _resolve_domain(sale_workflow.order_filter_domain)
            self._validate_sale_orders([('state', '=', 'draft')] + domain)
        if sale_workflow.create_invoice:
            domain = _resolve_domain(sale_workflow.create_invoice_filter_domain)
            self._create_invoices([('state', 'in', ['sale', 'done']), ('invoice_status', '=', 'to invoice')] + domain)
        if sale_workflow.validate_invoice:
            domain = _resolve_domain(sale_workflow.validate_invoice_filter_domain)
            self._validate_invoices([('state', '=', 'draft')] + domain)
        if sale_workflow.validate_picking:
            domain = _resolve_domain(sale_workflow.picking_filter_domain)
            self._validate_pickings([('state', 'in', ['draft', 'confirmed', 'assigned'])] + domain)
        if sale_workflow.sale_done:
            domain = _resolve_domain(sale_workflow.sale_done_filter_domain)
            self._sale_done([('state', '=', 'sale'), ('invoice_status', '=', 'invoiced')] + domain)

    @api.model
    def run(self):
        workflows = self.env['sale.workflow.process'].search([])
        for workflow in workflows:
            company = workflow.team_id.company_id or self.env.company
            self.with_company(company).run_with_workflow(workflow)
