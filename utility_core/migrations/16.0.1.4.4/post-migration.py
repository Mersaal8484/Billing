"""Backfill the current meter assignment without rewriting accounting history."""

from odoo import api, fields, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Customer = env['utility.customer'].with_context(active_test=False)
    Assignment = env['utility.customer.meter.assignment']
    for customer in Customer.search([('meter_id', '!=', False)]):
        if Assignment.search([
                ('customer_id', '=', customer.id),
                ('meter_id', '=', customer.meter_id.id),
        ], limit=1):
            continue
        Assignment.create({
            'customer_id': customer.id,
            'meter_id': customer.meter_id.id,
            'company_id': customer.company_id.id,
            'date_from': customer.create_date or fields.Datetime.now(),
            'initial_reading': customer.last_reading_value or 0.0,
            'assignment_type': 'migration',
            'reason': 'ترحيل تخصيص العداد الحالي',
            'state': 'open',
        })
