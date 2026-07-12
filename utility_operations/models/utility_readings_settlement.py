from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class UtilityReadingSettlement(models.Model):
    _name = 'utility.reading.settlement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = '??? ?????? ????????'
    _order = 'adjustment_date desc'

    name = fields.Char('??? ???????', default=lambda self: _('New'), readonly=True)
    reading_id = fields.Many2one('utility.reading', '??????? ?????????', required=True)
    meter_id = fields.Many2one('utility.meter', related='reading_id.meter_id', store=True)
    account_id = fields.Many2one('utility.customer', related='reading_id.account_id', store=True)
    sale_order_id = fields.Many2one('sale.order', '?????? ???????? ????????', compute='_compute_sale_order_id', store=True)

    old_value = fields.Float('??????? ???????', readonly=True)
    new_value = fields.Float('??????? ??????? ???????', required=True)
    old_consumption = fields.Float('????????? ??????', readonly=True)
    new_consumption = fields.Float('????????? ??????', compute='_compute_new_consumption')

    adjusted_by = fields.Many2one('res.users', '??? ??????? ??????', default=lambda self: self.env.user, readonly=True)
    adjustment_date = fields.Date('????? ???????', default=fields.Date.today, readonly=True)
    reason = fields.Text('??? ??????? ????????', required=True)

    state = fields.Selection([
        ('draft', '?????'),
        ('done', '??? ???????'),
    ], string='??????', default='draft', readonly=True)

    correction_move_id = fields.Many2one(
        'account.move', '????? ???????', readonly=True,
        help='????? ?????? ?? ?????? ??? ??????? ?? ???????'
    )

    def action_open_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('?????? ????????'),
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('reading_id')
    def _compute_sale_order_id(self):
        for record in self:
            if record.reading_id:
                order = self.env['sale.order'].search([
                    ('reading_id', '=', record.reading_id.id),
                    ('state', '!=', 'cancel'),
                ], limit=1)
                record.sale_order_id = order.id if order else False

    @api.depends('new_value', 'reading_id.previous_reading')
    def _compute_new_consumption(self):
        for record in self:
            if record.reading_id:
                record.new_consumption = record.new_value - (record.reading_id.previous_reading or 0.0)
            else:
                record.new_consumption = 0.0

    @api.onchange('reading_id')
    def _onchange_reading_id(self):
        if self.reading_id:
            self.old_value = self.reading_id.reading_value
            self.old_consumption = self.reading_id.consumption

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.reading.settlement') or _('New')
        return super().create(vals_list)

    def action_apply_settlement(self):
        self.ensure_one()
        if self.state == 'done':
            raise ValidationError(_('??? ??????? ?????? ??????!'))
        if self.reading_id.state != 'billed':
            raise ValidationError(_('???? ????? ???????? ???????? ??? ??? ???????! ?????? ???????: %s') % self.reading_id.state)

        old_value = self.reading_id.reading_value
        old_consumption = self.reading_id.consumption
        self.old_value = old_value
        self.old_consumption = old_consumption

        self.reading_id.with_context(_bypass_reading_protection=True).write({
            'reading_value': self.new_value,
        })

        if self.account_id:
            self.account_id.write({
                'last_reading_value': self.new_value,
                'last_reading_date': fields.Datetime.now(),
            })

        new_consumption = self.new_value - (self.reading_id.previous_reading or 0.0)
        delta_consumption = new_consumption - old_consumption
        if self.account_id and delta_consumption != 0:
            _logger.info(
                'Reading settlement %s changed consumption by %s kWh for account %s; accounting correction is handled by billing/accounting documents.',
                self.name, delta_consumption, self.account_id.customer_number)

        msg = _(
            'Reading settlement: %.2f -> %.2f (delta: %+.2f). Consumption: %.2f -> %.2f kWh. Reason: %s'
        ) % (
            old_value, self.new_value, self.new_value - old_value,
            old_consumption, new_consumption,
            self.reason,
        )
        self.reading_id.message_post(body=msg)

        if self.meter_id:
            self.env['utility.meter.log']._create_log(
                self.meter_id, 'settlement',
                _('Reading settlement: %.2f -> %.2f (delta: %+.2f). Reason: %s') % (
                    old_consumption, new_consumption, delta_consumption, self.reason),
                ref_record=self)

        self.write({'state': 'done'})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('????? ???????'),
                'message': _('?? ????? ????? ??????? ?????.'),
                'type': 'success',
                'sticky': False,
            }
        }
