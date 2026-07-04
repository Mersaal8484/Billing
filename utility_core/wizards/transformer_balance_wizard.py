from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityTransformerBalanceWizard(models.TransientModel):
    _name = 'utility.transformer.balance.wizard'
    _description = 'تقرير توازن المحول'

    transformer_id = fields.Many2one(
        'utility.transformer', string='المحول', required=True,
        domain=[('active', '=', True)]
    )
    date_from = fields.Date(
        string='من تاريخ', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1)
    )
    date_to = fields.Date(
        string='إلى تاريخ', required=True,
        default=fields.Date.context_today
    )
    show_loss_threshold = fields.Float('حد إنذار الفاقد %', default=10.0)

    coupling_meter_ids = fields.Many2many(
        'utility.meter', 'utility_transformer_balance_coupling_meter_rel',
        compute='_compute_meters', string='عدادات الربط'
    )
    child_meter_ids = fields.Many2many(
        'utility.meter', 'utility_transformer_balance_child_meter_rel',
        compute='_compute_meters', string='عدادات المشتركين'
    )

    total_supplied_kwh = fields.Float('الطاقة الموردة (kWh)', compute='_compute_balance')
    total_consumed_kwh = fields.Float('الطاقة المستهلكة (kWh)', compute='_compute_balance')
    total_loss_kwh = fields.Float('الفاقد (kWh)', compute='_compute_balance')
    loss_percentage = fields.Float('نسبة الفاقد %', compute='_compute_balance')
    is_loss_warning = fields.Boolean('تحذير الفاقد', compute='_compute_balance')

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_('تاريخ البداية يجب أن يكون قبل أو يساوي تاريخ النهاية.'))

    @api.depends('transformer_id')
    def _compute_meters(self):
        Meter = self.env['utility.meter']
        for wizard in self:
            if not wizard.transformer_id:
                wizard.coupling_meter_ids = False
                wizard.child_meter_ids = False
                continue
            meters = Meter.search([
                ('transformer_id', '=', wizard.transformer_id.id),
                ('active', '=', True),
            ])
            wizard.coupling_meter_ids = [(6, 0, meters.filtered('is_coupling_meter').ids)]
            wizard.child_meter_ids = [(6, 0, meters.filtered(lambda m: not m.is_coupling_meter).ids)]

    @api.depends('date_from', 'date_to', 'show_loss_threshold', 'coupling_meter_ids', 'child_meter_ids')
    def _compute_balance(self):
        for wizard in self:
            values = wizard._prepare_balance_values()
            totals = values['totals']
            wizard.total_supplied_kwh = totals['supplied']
            wizard.total_consumed_kwh = totals['consumed']
            wizard.total_loss_kwh = totals['loss']
            wizard.loss_percentage = totals['loss_percentage']
            wizard.is_loss_warning = totals['is_loss_warning']

    def _reading_date_domain(self):
        self.ensure_one()
        date_from = fields.Datetime.to_string(fields.Datetime.to_datetime(self.date_from))
        date_to = fields.Datetime.to_string(fields.Datetime.to_datetime(self.date_to) + timedelta(days=1, seconds=-1))
        return [
            ('reading_date', '>=', date_from),
            ('reading_date', '<=', date_to),
            ('state', 'in', ['approved', 'billed']),
        ]

    def _latest_reading_by_meter(self, meters):
        self.ensure_one()
        latest = {}
        if not meters:
            return latest
        readings = self.env['utility.reading'].search(
            [('meter_id', 'in', meters.ids)] + self._reading_date_domain(),
            order='meter_id, reading_date desc, id desc'
        )
        for reading in readings:
            latest.setdefault(reading.meter_id.id, reading)
        return latest

    def _prepare_meter_lines(self, meters, latest_map):
        lines = []
        for meter in meters.sorted(lambda m: (m.meter_number or '', m.id)):
            reading = latest_map.get(meter.id)
            consumption = max(reading.consumption, 0.0) if reading else 0.0
            lines.append({
                'meter': meter,
                'customer': meter.customer_id,
                'reading': reading,
                'consumption': consumption,
                'has_reading': bool(reading),
            })
        return lines

    def _prepare_balance_values(self):
        self.ensure_one()
        coupling_latest = self._latest_reading_by_meter(self.coupling_meter_ids)
        child_latest = self._latest_reading_by_meter(self.child_meter_ids)
        coupling_lines = self._prepare_meter_lines(self.coupling_meter_ids, coupling_latest)
        child_lines = self._prepare_meter_lines(self.child_meter_ids, child_latest)

        supplied = sum(line['consumption'] for line in coupling_lines)
        consumed = sum(line['consumption'] for line in child_lines)
        loss = supplied - consumed
        loss_percentage = (loss / supplied * 100.0) if supplied > 0 else 0.0
        return {
            'coupling_lines': coupling_lines,
            'child_lines': child_lines,
            'totals': {
                'supplied': supplied,
                'consumed': consumed,
                'loss': loss,
                'loss_percentage': loss_percentage,
                'is_loss_warning': supplied > 0 and loss_percentage >= self.show_loss_threshold,
            },
        }

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref('utility_core.action_report_transformer_balance').report_action(self)