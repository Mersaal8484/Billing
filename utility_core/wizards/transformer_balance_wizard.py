import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class UtilityTransformerBalanceWizard(models.TransientModel):
    _name = 'utility.transformer.balance.wizard'
    _description = 'Transformer Balance Report Wizard'

    transformer_id = fields.Many2one('utility.transformer', 'المحول',
        required=True, domain="[('active', '=', True)]")
    date_from = fields.Date('من تاريخ', required=True,
        default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date('إلى تاريخ', required=True,
        default=fields.Date.today)
    
    # استخدام Many2many لتجنب متطلبات الحقل العكسي One2many
    coupling_meter_ids = fields.Many2many('utility.meter', 'relation_coupling_meters_wizard_rel',
        compute='_compute_meters', string='عدادات الربط')
    child_meter_ids = fields.Many2many('utility.meter', 'relation_child_meters_wizard_rel',
        compute='_compute_meters', string='عدادات المشتركين')
    
    total_supplied_kwh = fields.Float('الطاقة الموردة (kWh)',
        compute='_compute_balance', store=True)
    total_consumed_kwh = fields.Float('الطاقة المستهلكة (kWh)',
        compute='_compute_balance', store=True)
    total_loss_kwh = fields.Float('الفاقد (kWh)',
        compute='_compute_balance', store=True)
    loss_percentage = fields.Float('نسبة الفاقد %',
        compute='_compute_balance', store=True)
    
    show_cells = fields.Boolean('إظهار الخلايا', default=True)
    show_loss_threshold = fields.Float('حد الإنذار للفاقد %', default=10.0,
        help='إذا تجاوز الفاقد هذه النسبة يظهر إنذار أحمر')

    @api.depends('transformer_id')
    def _compute_meters(self):
        for rec in self:
            transformer = rec.transformer_id
            if not transformer:
                rec.coupling_meter_ids = False
                rec.child_meter_ids = False
                continue
            
            # عدادات الربط
            coupling = self.env['utility.meter'].search([
                ('transformer_id', '=', transformer.id),
                ('is_coupling_meter', '=', True),
            ])
            rec.coupling_meter_ids = [(6, 0, coupling.ids)]
            
            # عدادات المشتركين
            children = self.env['utility.meter'].search([
                ('transformer_id', '=', transformer.id),
                ('is_coupling_meter', '=', False),
            ])
            rec.child_meter_ids = [(6, 0, children.ids)]

    @api.depends('date_from', 'date_to', 'transformer_id', 'coupling_meter_ids', 'child_meter_ids')
    def _compute_balance(self):
        Reading = self.env['utility.reading']
        for rec in self:
            coupling_meters = rec.coupling_meter_ids
            child_meters = rec.child_meter_ids
            
            # تجميع حسب العداد (آخر قراءة في الفترة لكل عداد)
            supplied = 0.0
            consumed = 0.0
            
            for meter in coupling_meters:
                last = Reading.search([
                    ('meter_id', '=', meter.id),
                    ('reading_date', '>=', rec.date_from),
                    ('reading_date', '<=', rec.date_to),
                    ('state', 'in', ['approved', 'billed']),
                ], order='reading_date desc', limit=1)
                if last and last.consumption > 0:
                    supplied += last.consumption
            
            for meter in child_meters:
                last = Reading.search([
                    ('meter_id', '=', meter.id),
                    ('reading_date', '>=', rec.date_from),
                    ('reading_date', '<=', rec.date_to),
                    ('state', 'in', ['approved', 'billed']),
                ], order='reading_date desc', limit=1)
                if last and last.consumption > 0:
                    consumed += last.consumption
            
            rec.total_supplied_kwh = supplied
            rec.total_consumed_kwh = consumed
            rec.total_loss_kwh = supplied - consumed
            if supplied > 0:
                rec.loss_percentage = (rec.total_loss_kwh / supplied) * 100
            else:
                rec.loss_percentage = 0.0

    def action_print_report(self):
        """طباعة تقرير توازن المحول"""
        return self.env.ref('utility_core.action_report_transformer_balance').report_action(self)
