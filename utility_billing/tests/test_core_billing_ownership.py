from odoo.tests.common import TransactionCase


class TestCoreBillingOwnership(TransactionCase):
    """Regression coverage for the Core/Billing reading ownership boundary."""

    def test_billing_fields_extend_the_core_reading_model(self):
        reading_model = self.env['utility.reading']
        billing_fields = {
            'is_billable',
            'billing_anchor_id',
            'billing_component_ids',
            'included_sale_order_id',
            'carried_consumption',
            'billing_consumption',
            'billing_error',
        }

        self.assertTrue(billing_fields.issubset(reading_model._fields))
        self.assertEqual(reading_model._name, 'utility.reading')
        self.assertTrue(reading_model.new({
            'reading_category': 'customer',
            'reading_purpose': 'periodic',
        })._requires_billing_review())

    def test_billing_computes_preserve_existing_reading_semantics(self):
        reading = self.env['utility.reading'].new({
            'reading_category': 'customer',
            'reading_purpose': 'periodic',
            'consumption': 125.0,
        })

        reading._compute_is_billable()
        reading._compute_billing_consumption()

        self.assertTrue(reading.is_billable)
        self.assertEqual(reading.carried_consumption, 0.0)
        self.assertEqual(reading.billing_consumption, 125.0)

    def test_non_periodic_readings_remain_non_billable(self):
        reading = self.env['utility.reading'].new({
            'reading_category': 'customer',
            'reading_purpose': 'opening',
            'consumption': 125.0,
        })

        reading._compute_is_billable()
        reading._compute_billing_consumption()

        self.assertFalse(reading.is_billable)
        self.assertEqual(reading.billing_consumption, 0.0)
