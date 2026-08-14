from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, ValidationError, UserError


class TestContractTemplateCloneWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Users and Groups
        cls.group_billing_manager = cls.env.ref('utility_core.group_utility_billing_manager')
        cls.group_admin = cls.env.ref('utility_core.group_utility_admin')
        cls.group_reader = cls.env.ref('utility_core.group_utility_meter_reader')

        cls.user_manager = cls.env['res.users'].create({
            'name': 'Billing Manager Test',
            'login': 'billing_mgr_clone_test',
            'email': 'mgr_clone@test.com',
            'groups_id': [(6, 0, [cls.group_billing_manager.id])],
        })

        cls.user_reader = cls.env['res.users'].create({
            'name': 'Meter Reader Test',
            'login': 'meter_reader_clone_test',
            'email': 'reader_clone@test.com',
            'groups_id': [(6, 0, [cls.group_reader.id])],
        })

        # Subscriber Category & Subscriber
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'Residential Category',
            'code': 'RES-CAT-CLONE',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'Residential Subscriber',
            'code': 'RES-SUB-CLONE',
            'category_id': cls.category.id,
        })

        # Regions
        cls.region_a = cls.env['utility.region'].create({
            'name': 'Region North',
            'code': 'REG-N-CLONE',
            'type': 'region',
        })
        cls.area_a = cls.env['utility.region'].create({
            'name': 'Branch North 1',
            'code': 'BR-N1-CLONE',
            'type': 'area',
            'parent_id': cls.region_a.id,
        })
        cls.region_b = cls.env['utility.region'].create({
            'name': 'Region South',
            'code': 'REG-S-CLONE',
            'type': 'region',
        })
        cls.area_b = cls.env['utility.region'].create({
            'name': 'Branch South 1',
            'code': 'BR-S1-CLONE',
            'type': 'area',
            'parent_id': cls.region_b.id,
        })

        # Formula & Products
        cls.kwh_product = cls.env.ref('utility_core.utility_product_kwh', raise_if_not_found=False)
        if not cls.kwh_product:
            cls.kwh_product = cls.env['product.product'].create({
                'name': 'Electricity kWh',
                'type': 'service',
            })
        cls.service_product = cls.env.ref('utility_core.utility_product_service_charge', raise_if_not_found=False)
        if not cls.service_product:
            cls.service_product = cls.env['product.product'].create({
                'name': 'Service Charge',
                'type': 'service',
            })

        cls.formula = cls.env['utility.formula'].create({
            'name': 'Dynamic Discount Formula',
            'code': 'DISC_FORMULA_CLONE',
            'expression': 'consumption * 0.10',
        })

        # Master Source Template
        cls.source_template = cls.env['utility.contract.template'].create({
            'name': 'Master Commercial Tariff',
            'code': 'COMM-MASTER-2026',
            'pricing_mode': 'block',
            'price_per_kwh': 200.0,
            'service_charge': 1500.0,
            'min_charge': 500.0,
            'max_charge': 50000.0,
            'local_fee_per_kwh': 5.0,
            'local_fee_mu_allim': 2.0,
            'local_fee_cleaning': 3.0,
            'scope': 'restricted',
            'region_ids': [(6, 0, [cls.region_a.id])],
            'area_ids': [(6, 0, [cls.area_a.id])],
            'subscriber_category_ids': [(6, 0, [cls.category.id])],
            'subscriber_ids': [(6, 0, [cls.subscriber.id])],
            'sale_autoconfirm': True,
            'create_invoice_automatically': True,
            'validate_invoice_automatically': False,
            'recurring_rule_type': 'monthly',
            'recurring_invoicing_type': 'postpaid',
            'discount_formula_id': cls.formula.id,
        })
        cls.env['utility.contract.template.line'].create([
            {
                'template_id': cls.source_template.id,
                'sequence': 10,
                'product_id': cls.kwh_product.id,
                'name': 'استهلاك كهرباء تجاري',
                'price_type': 'meter_reading',
                'meter_line_type': 'consumption',
                'specific_price': 200.0,
            },
            {
                'template_id': cls.source_template.id,
                'sequence': 20,
                'product_id': cls.service_product.id,
                'name': 'رسم خدمة ثابت',
                'price_type': 'fixed',
                'meter_line_type': 'service_charge',
                'specific_price': 1500.0,
            }
        ])

        # Blocks on source template
        cls.env['utility.contract.template.block'].create([
            {
                'template_id': cls.source_template.id,
                'sequence': 10,
                'name': 'الشريحة الأولى (0-500)',
                'from_kwh': 0,
                'to_kwh': 500,
                'price_per_kwh': 180.0,
                'is_discount': False,
            },
            {
                'template_id': cls.source_template.id,
                'sequence': 20,
                'name': 'الشريحة الثانية (500+)',
                'from_kwh': 500,
                'to_kwh': 0,
                'price_per_kwh': 220.0,
                'is_discount': False,
            },
            {
                'template_id': cls.source_template.id,
                'sequence': 30,
                'name': 'شريحة خصم مدعوم',
                'from_kwh': 0,
                'to_kwh': 100,
                'price_per_kwh': 50.0,
                'is_discount': True,
            }
        ])

    def test_01_full_clone_with_all_options(self):
        """Verify complete configuration cloning creating an independent template."""
        wizard = self.env['utility.contract.template.clone.wizard'].with_user(self.user_manager).create({
            'source_template_id': self.source_template.id,
            'new_name': 'Commercial Tariff Branch South',
            'new_code': 'COMM-SOUTH-2026',
            'copy_pricing': True,
            'copy_contract_lines': True,
            'copy_pricing_blocks': True,
            'copy_discount_blocks': True,
            'copy_discount_configuration': True,
            'copy_local_fees': True,
            'copy_scope': True,
            'copy_workflow_settings': True,
            'target_scope': 'restricted',
            'target_region_ids': [(6, 0, [self.region_b.id])],
            'target_area_ids': [(6, 0, [self.area_b.id])],
        })

        action = wizard.action_clone_template()
        new_template_id = action['res_id']
        new_template = self.env['utility.contract.template'].browse(new_template_id)

        # 1. Identity & Provenance
        self.assertEqual(new_template.name, 'Commercial Tariff Branch South')
        self.assertEqual(new_template.code, 'COMM-SOUTH-2026')
        self.assertEqual(new_template.cloned_from_template_id.id, self.source_template.id)
        self.assertTrue(new_template.cloned_at)
        self.assertEqual(new_template.cloned_by.id, self.user_manager.id)

        # 2. Commercial Pricing & Local Fees
        self.assertEqual(new_template.pricing_mode, 'block')
        self.assertEqual(new_template.price_per_kwh, 200.0)
        self.assertEqual(new_template.service_charge, 1500.0)
        self.assertEqual(new_template.min_charge, 500.0)
        self.assertEqual(new_template.max_charge, 50000.0)
        self.assertEqual(new_template.local_fee_per_kwh, 5.0)
        self.assertEqual(new_template.local_fee_mu_allim, 2.0)
        self.assertEqual(new_template.local_fee_cleaning, 3.0)

        # 3. Children (Lines & Blocks)
        self.assertEqual(len(new_template.line_ids), len(self.source_template.line_ids))
        self.assertEqual(len(new_template.block_ids), 2)
        self.assertEqual(len(new_template.discount_block_ids), 1)

        # 4. Subscriber Configuration (Always copied from source)
        self.assertEqual(new_template.subscriber_category_ids.ids, self.source_template.subscriber_category_ids.ids)
        self.assertEqual(new_template.subscriber_ids.ids, self.source_template.subscriber_ids.ids)

        # 5. Geographic Scope Override applied (copy_scope=True with target_region_ids=region_b)
        self.assertEqual(new_template.scope, 'restricted')
        self.assertIn(self.region_b.id, new_template.region_ids.ids)
        self.assertIn(self.area_b.id, new_template.area_ids.ids)

    def test_02_new_identity_and_unique_code_enforcement(self):
        """Verify that empty names or duplicate codes are rejected."""
        # Empty name
        with self.assertRaises(ValidationError):
            wizard = self.env['utility.contract.template.clone.wizard'].with_user(self.user_manager).create({
                'source_template_id': self.source_template.id,
                'new_name': '',
                'new_code': 'UNIQUE-CODE-001',
            })
            wizard.action_clone_template()

        # Duplicate code
        with self.assertRaises(ValidationError):
            wizard = self.env['utility.contract.template.clone.wizard'].with_user(self.user_manager).create({
                'source_template_id': self.source_template.id,
                'new_name': 'Duplicate Code Template',
                'new_code': self.source_template.code,
            })
            wizard.action_clone_template()

    def test_03_child_independence(self):
        """Verify modifying cloned blocks or lines does NOT mutate the source template."""
        wizard = self.env['utility.contract.template.clone.wizard'].with_user(self.user_manager).create({
            'source_template_id': self.source_template.id,
            'new_name': 'Independent Test Template',
            'new_code': 'INDEP-TEST-001',
        })
        action = wizard.action_clone_template()
        new_template = self.env['utility.contract.template'].browse(action['res_id'])

        # Modify cloned block price
        cloned_b1 = new_template.block_ids[0]
        cloned_b1.write({'price_per_kwh': 999.0})

        source_b1 = self.source_template.block_ids.filtered(lambda b: b.from_kwh == cloned_b1.from_kwh)
        self.assertEqual(source_b1.price_per_kwh, 180.0)
        self.assertEqual(cloned_b1.price_per_kwh, 999.0)

        # Modify source line
        source_l1 = self.source_template.line_ids[0]
        source_l1.write({'specific_price': 555.0})

        cloned_l1 = new_template.line_ids[0]
        self.assertNotEqual(cloned_l1.specific_price, 555.0)

    def test_04_formula_and_product_references_preserved(self):
        """Verify shared master data references (formulas, products) are preserved and not duplicated."""
        formula_count_before = self.env['utility.formula'].search_count([('code', '=', 'DISC_FORMULA_CLONE')])
        wizard = self.env['utility.contract.template.clone.wizard'].with_user(self.user_manager).create({
            'source_template_id': self.source_template.id,
            'new_name': 'Formula Ref Test',
            'new_code': 'FORM-REF-001',
        })
        action = wizard.action_clone_template()
        new_template = self.env['utility.contract.template'].browse(action['res_id'])

        formula_count_after = self.env['utility.formula'].search_count([('code', '=', 'DISC_FORMULA_CLONE')])
        self.assertEqual(formula_count_before, formula_count_after)
        self.assertEqual(new_template.discount_formula_id.id, self.formula.id)

    def test_05_history_isolation(self):
        """Verify source pricing history is NOT copied to the new template."""
        # Create history on source template by updating price
        self.source_template.write({'price_per_kwh': 250.0})
        self.assertTrue(self.source_template.history_ids)

        wizard = self.env['utility.contract.template.clone.wizard'].with_user(self.user_manager).create({
            'source_template_id': self.source_template.id,
            'new_name': 'History Isolation Test',
            'new_code': 'HIST-ISO-001',
        })
        action = wizard.action_clone_template()
        new_template = self.env['utility.contract.template'].browse(action['res_id'])

        self.assertFalse(new_template.history_ids)

    def test_06_version_isolation(self):
        """Verify cloned template starts fresh at Version 1, not inheriting source versions."""
        # Simulate source template having active version
        v1 = self.source_template._get_or_create_active_version()
        self.assertTrue(v1)

        wizard = self.env['utility.contract.template.clone.wizard'].with_user(self.user_manager).create({
            'source_template_id': self.source_template.id,
            'new_name': 'Version Isolation Test',
            'new_code': 'VER-ISO-001',
        })
        action = wizard.action_clone_template()
        new_template = self.env['utility.contract.template'].browse(action['res_id'])

        self.assertEqual(new_template.version_count, 1)
        self.assertEqual(new_template.current_version_id.version_number, 1)
        self.assertEqual(new_template.current_version_id.version_code, 'VER-ISO-001-V1')
        self.assertFalse(new_template.current_version_id.is_used_in_billing)

    def test_07_security_unauthorized_user_blocked(self):
        """Verify non-manager and non-admin users cannot clone contract templates."""
        wizard = self.env['utility.contract.template.clone.wizard'].with_user(self.user_reader).create({
            'source_template_id': self.source_template.id,
            'new_name': 'Unauthorized Clone',
            'new_code': 'UNAUTH-001',
        })
        with self.assertRaises(AccessError):
            wizard.action_clone_template()
