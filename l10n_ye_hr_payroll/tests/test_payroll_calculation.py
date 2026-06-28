from odoo.tests.common import TransactionCase


class TestYemeniPayroll(TransactionCase):

    def setUp(self):
        super(TestYemeniPayroll, self).setUp()
        self.company = self.env.company
        
        # Ensure we have active tax brackets
        self.tax_bracket_model = self.env['ye.tax.bracket']
        self.first_bracket = self.tax_bracket_model.search([
            ('company_id', '=', self.company.id),
            ('rate', '=', 0.0),
            ('active', '=', True)
        ], order='from_amount asc', limit=1)

        # Create a test employee
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Yemeni Employee',
            'company_id': self.company.id,
        })

        # Get structure type (loaded on module install)
        self.struct_type = self.env.ref('l10n_ye_hr_payroll.ye_structure_type')

        # Create a test contract
        self.contract = self.env['hr.contract'].create({
            'name': 'Test Contract',
            'employee_id': self.employee.id,
            'wage': 30000.0,
            'housing_allowance': 5000.0,
            'transport_allowance': 3000.0,
            'other_allowance': 2000.0,
            'social_insurance_number': '12345678',
            'company_id': self.company.id,
            'structure_type_id': self.struct_type.id,
            'state': 'open',
            'date_start': '2026-01-01',
        })

    def test_01_tax_exemption_sync(self):
        """ Test bidirectional synchronization between company tax_exemption_amount and 0% bracket's to_amount. """
        if not self.first_bracket:
            # Create a 0% bracket if it wasn't loaded in test mode
            self.first_bracket = self.tax_bracket_model.create({
                'name': 'Exempt (0%)',
                'from_amount': 0.0,
                'to_amount': 10000.0,
                'rate': 0.0,
                'company_id': self.company.id,
            })

        # 1. Update company settings -> bracket should update
        self.company.write({'tax_exemption_amount': 12000.0})
        self.assertEqual(self.first_bracket.to_amount, 12000.0)

        # 2. Update bracket to_amount -> company settings should update
        self.first_bracket.write({'to_amount': 15000.0})
        self.assertEqual(self.company.tax_exemption_amount, 15000.0)

    def test_02_progressive_tax_computation(self):
        """ Test progressive tax calculation logic directly. """
        # Reset company exemption to 10000.0 to match standard
        self.company.write({'tax_exemption_amount': 10000.0})
        
        # Base amount: 25000 (Gross - Insurable)
        # Tax should be:
        # 0-10k: 0
        # 10k-25k: 15k * 0.10 = 1500
        tax_25 = self.tax_bracket_model.compute_tax(25000.0, self.company.id)
        self.assertEqual(tax_25, 1500.0)

        # Base amount: 45000
        # Tax:
        # 0-10k: 0
        # 10k-30k: 20k * 0.10 = 2000
        # 30k-45k: 15k * 0.15 = 2250
        # Total = 4250
        tax_45 = self.tax_bracket_model.compute_tax(45000.0, self.company.id)
        self.assertEqual(tax_45, 4250.0)

        # Base amount: 85000
        # Tax:
        # 0-10k: 0
        # 10k-30k: 2000
        # 30k-60k: 30k * 0.15 = 4500
        # 60k-85k: 25k * 0.20 = 5000
        # Total = 11500
        tax_85 = self.tax_bracket_model.compute_tax(85000.0, self.company.id)
        self.assertEqual(tax_85, 11500.0)

    def test_03_payslip_calculation(self):
        """ Test full payslip generation and verify rules computation. """
        # Reset company settings to defaults
        self.company.write({
            'tax_exemption_amount': 10000.0,
            'social_insurance_employee_rate': 6.0,
            'social_insurance_employer_rate': 9.0,
            'social_insurance_min_base': 0.0,
            'social_insurance_max_base': 0.0,
        })
        
        # Create a payslip
        payslip = self.env['hr.payslip'].create({
            'name': 'Test Payslip',
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'struct_id': self.env.ref('l10n_ye_hr_payroll.ye_structure_base').id,
            'date_from': '2026-06-01',
            'date_to': '2026-06-30',
        })
        
        # Trigger compute
        payslip.compute_sheet()
        
        # Verify lines
        line_dict = {line.code: line.total for line in payslip.line_ids}
        self.assertAlmostEqual(line_dict.get('BASIC'), 30000.0, places=2)
        self.assertAlmostEqual(line_dict.get('HOUSING_ALW'), 5000.0, places=2)
        self.assertAlmostEqual(line_dict.get('TRANSPORT_ALW'), 3000.0, places=2)
        self.assertAlmostEqual(line_dict.get('OTHER_ALW'), 2000.0, places=2)
        self.assertAlmostEqual(line_dict.get('GROSS'), 40000.0, places=2)
        self.assertAlmostEqual(line_dict.get('EMP_INS'), -2280.0, places=2)
        self.assertAlmostEqual(line_dict.get('TAX'), -3158.0, places=2)
        self.assertAlmostEqual(line_dict.get('NET'), 34562.0, places=2)

    def test_04_demo_scenario_calculation(self):
        """ Test payroll calculation specifically for the Yemeni demo employee (Ahmed Al-Hashedi). """
        # Find the demo contract from xmlid
        contract = self.env.ref('l10n_ye_hr_payroll.ye_contract_ahmed', raise_if_not_found=False)
        if not contract:
            return

        # Ensure company settings match the standard scenario
        self.company.write({
            'tax_exemption_amount': 10000.0,
            'social_insurance_employee_rate': 6.0,
            'social_insurance_employer_rate': 9.0,
            'social_insurance_min_base': 0.0,
            'social_insurance_max_base': 0.0,
        })

        # Create a payslip for Ahmed Al-Hashedi
        payslip = self.env['hr.payslip'].create({
            'name': 'مسير رواتب - أحمد محمد الحاشدي',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'struct_id': self.env.ref('l10n_ye_hr_payroll.ye_structure_base').id,
            'date_from': '2026-06-01',
            'date_to': '2026-06-30',
        })

        payslip.compute_sheet()

        line_dict = {line.code: line.total for line in payslip.line_ids}

        # BASIC: 450,000.0
        # HOUSING_ALW: 80,000.0
        # TRANSPORT_ALW: 40,000.0
        # OTHER_ALW: 30,000.0
        # GROSS: 600,000.0
        # EMP_INS: -34,200.0
        # TAX: -107,660.0
        # NET: 458,140.0
        # COMPANY_INS (Employer): 51,300.0
        # EOS_PROV: 37,500.0

        self.assertAlmostEqual(line_dict.get('BASIC'), 450000.0, places=2)
        self.assertAlmostEqual(line_dict.get('HOUSING_ALW'), 80000.0, places=2)
        self.assertAlmostEqual(line_dict.get('TRANSPORT_ALW'), 40000.0, places=2)
        self.assertAlmostEqual(line_dict.get('OTHER_ALW'), 30000.0, places=2)
        self.assertAlmostEqual(line_dict.get('GROSS'), 600000.0, places=2)
        self.assertAlmostEqual(line_dict.get('EMP_INS'), -34200.0, places=2)
        self.assertAlmostEqual(line_dict.get('TAX'), -107660.0, places=2)
        self.assertAlmostEqual(line_dict.get('NET'), 458140.0, places=2)
        self.assertAlmostEqual(line_dict.get('COMPANY_INS'), 51300.0, places=2)
        self.assertAlmostEqual(line_dict.get('EOS_PROV'), 37500.0, places=2)

