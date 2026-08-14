from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'utility_release', 'utility_security')
class TestSensitiveWizardPermissions(TransactionCase):

    def setUp(self):
        super().setUp()
        self.internal_user = self.env['res.users'].create({
            'name': 'مستخدم داخلي بلا صلاحيات تشغيلية',
            'login': 'utility_wizard_restricted',
            'email': 'utility_wizard_restricted@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.supervisor = self.env['res.users'].create({
            'name': 'مشرف اختبارات المعالجات',
            'login': 'utility_wizard_supervisor',
            'email': 'utility_wizard_supervisor@example.com',
            'groups_id': [
                (6, 0, [
                    self.env.ref('base.group_user').id,
                    self.env.ref('utility_core.group_utility_supervisor').id,
                ]),
            ],
        })

    def test_internal_user_cannot_create_sensitive_wizards(self):
        """Broad base.group_user wizard access must stay closed."""
        restricted_models = [
            'utility.customer.wizard',
            'utility.route.add.customer.wizard',
            'utility.route.remove.customer.wizard',
            'utility.meter.subscriber.wizard',
            'utility.meter.private.transformer.wizard',
            'utility.meter.transformer.wizard',
            'utility.meter.feeder.wizard',
            'utility.meter.replace.wizard',
        ]
        for model_name in restricted_models:
            model = self.env[model_name].with_user(self.internal_user)
            self.assertFalse(
                model.check_access_rights('create', raise_exception=False),
                model_name,
            )

    def test_supervisor_can_use_operational_wizards_but_not_network_creation(self):
        """Supervisor ACLs match mutations: operations yes, feeder/transformer no."""
        for model_name in (
            'utility.customer.wizard',
            'utility.route.add.customer.wizard',
            'utility.route.remove.customer.wizard',
            'utility.meter.subscriber.wizard',
            'utility.meter.replace.wizard',
        ):
            self.assertTrue(
                self.env[model_name].with_user(self.supervisor).check_access_rights(
                    'create', raise_exception=False
                ),
                model_name,
            )

        for model_name in (
            'utility.meter.private.transformer.wizard',
            'utility.meter.transformer.wizard',
            'utility.meter.feeder.wizard',
        ):
            self.assertFalse(
                self.env[model_name].with_user(self.supervisor).check_access_rights(
                    'create', raise_exception=False
                ),
                model_name,
            )

    def test_server_side_guard_rejects_restricted_customer_wizard(self):
        """The action guard remains effective independently of ACL configuration."""
        wizard = self.env['utility.customer.wizard'].with_user(self.internal_user).new({})
        with self.assertRaises(AccessError):
            wizard.action_create_customer()
