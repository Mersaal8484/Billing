from odoo.tests.common import TransactionCase


class TestConstructionProject(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Project = self.env['construction.project']
        self.Boq = self.env['construction.boq']
        self.BoqItem = self.env['construction.boq.item']
        self.Resource = self.env['construction.resource']
        self.RateAnalysis = self.env['construction.rate.analysis']
        self.RateLine = self.env['construction.rate.analysis.line']

        self.uom_unit = self.env.ref('uom.product_uom_unit')
        self.company = self.env.company

        self.project = self.Project.create({
            'name': 'Test Project',
            'code': 'TEST-001',
            'company_id': self.company.id,
        })

    def test_01_project_creation(self):
        self.assertTrue(self.project.name)
        self.assertEqual(self.project.code, 'TEST-001')
        self.assertEqual(self.project.project_stage, 'planning')
        self.assertTrue(self.project.company_id)

    def test_02_project_boq_count(self):
        boq = self.Boq.create({
            'name': 'Test BOQ',
            'code': 'BOQ-001',
            'project_id': self.project.id,
        })
        self.project.invalidate_recordset(['boq_count'])
        self.assertEqual(self.project.boq_count, 1)

    def test_03_boq_item_amount(self):
        boq = self.Boq.create({
            'name': 'Test BOQ',
            'code': 'BOQ-002',
            'project_id': self.project.id,
        })
        item = self.BoqItem.create({
            'boq_id': boq.id,
            'code': '1.1',
            'name': 'Excavation',
            'unit': self.uom_unit.id,
            'quantity': 100.0,
            'rate': 50.0,
        })
        self.assertEqual(item.amount, 5000.0)

    def test_04_boq_item_executed_percent(self):
        boq = self.Boq.create({
            'name': 'Test BOQ',
            'code': 'BOQ-003',
            'project_id': self.project.id,
        })
        item = self.BoqItem.create({
            'boq_id': boq.id,
            'code': '1.2',
            'name': 'Concrete',
            'unit': self.uom_unit.id,
            'quantity': 200.0,
            'rate': 100.0,
        })
        self.assertEqual(item.executed_percent, 0.0)
        item.executed_quantity = 50.0
        self.assertEqual(item.executed_percent, 25.0)
        self.assertEqual(item.remaining_quantity, 150.0)

    def test_05_rate_analysis_calculation(self):
        resource = self.Resource.create({
            'name': 'Test Labor',
            'code': 'LAB-TEST',
            'resource_type': 'labor',
            'uom_id': self.uom_unit.id,
            'unit_cost': 100.0,
            'overhead_percent': 5.0,
            'profit_percent': 10.0,
        })
        boq = self.Boq.create({
            'name': 'BOQ Rate Test',
            'code': 'BOQ-RATE',
            'project_id': self.project.id,
        })
        item = self.BoqItem.create({
            'boq_id': boq.id,
            'code': '1.3',
            'name': 'Test Item',
            'unit': self.uom_unit.id,
            'quantity': 10.0,
            'rate': 0.0,
        })
        analysis = self.RateAnalysis.create({
            'boq_item_id': item.id,
            'markup_percent': 5.0,
            'profit_percent': 10.0,
        })
        self.RateLine.create({
            'rate_analysis_id': analysis.id,
            'resource_id': resource.id,
            'resource_type': 'labor',
            'quantity': 1.0,
            'unit_cost': 100.0,
        })
        self.assertEqual(analysis.direct_cost, 100.0)
        self.assertAlmostEqual(analysis.final_rate, 115.5, places=1)

    def test_06_material_request_workflow(self):
        MaterialRequest = self.env['construction.material.request']
        MaterialRequestLine = self.env['construction.material.request.line']
        mr = MaterialRequest.create({
            'project_id': self.project.id,
            'date': '2024-01-01',
        })
        MaterialRequestLine.create({
            'request_id': mr.id,
            'product_id': self.env.ref('product.product_delivery_01').id,
            'quantity': 10.0,
        })
        self.assertEqual(mr.state, 'draft')
        mr.action_submit()
        self.assertEqual(mr.state, 'submitted')
        mr.action_approve()
        self.assertEqual(mr.state, 'approved')

    def test_07_variation_workflow(self):
        Variation = self.env['construction.variation']
        boq = self.Boq.create({
            'name': 'Var BOQ',
            'code': 'BOQ-VAR',
            'project_id': self.project.id,
        })
        item = self.BoqItem.create({
            'boq_id': boq.id,
            'code': 'VAR.1',
            'name': 'Variation Item',
            'unit': self.uom_unit.id,
            'quantity': 10.0,
            'rate': 100.0,
        })
        var = Variation.create({
            'project_id': self.project.id,
            'description': 'Test Variation',
            'variation_type': 'client',
        })
        self.env['construction.variation.line'].create({
            'variation_id': var.id,
            'boq_item_id': item.id,
            'original_quantity': 10.0,
            'revised_quantity': 15.0,
            'original_rate': 100.0,
            'revised_rate': 100.0,
        })
        var.action_submit()
        self.assertEqual(var.state, 'submitted')
        var.action_review()
        self.assertEqual(var.state, 'review')
        var.action_approve()
        self.assertEqual(var.state, 'approved')
        self.assertEqual(var.net_change, 500.0)

    def test_08_ipc_workflow(self):
        Ipc = self.env['construction.ipc']
        IpcLine = self.env['construction.ipc.line']
        boq = self.Boq.create({
            'name': 'IPC BOQ', 'code': 'BOQ-IPC',
            'project_id': self.project.id,
        })
        item = self.BoqItem.create({
            'boq_id': boq.id, 'code': 'IPC.1', 'name': 'IPC Item',
            'unit': self.uom_unit.id, 'quantity': 100.0, 'rate': 500.0,
        })
        ipc = Ipc.create({
            'project_id': self.project.id,
            'period_from': '2024-01-01',
            'period_to': '2024-03-31',
            'date': '2024-04-01',
        })
        IpcLine.create({
            'ipc_id': ipc.id, 'boq_item_id': item.id,
            'current_quantity': 50.0, 'rate': 500.0,
        })
        self.assertEqual(ipc.state, 'draft')
        ipc.action_submit()
        self.assertEqual(ipc.state, 'submitted')
        ipc.action_review()
        self.assertEqual(ipc.state, 'reviewed')
        ipc.action_certify()
        self.assertEqual(ipc.state, 'certified')
        ipc.action_approve()
        self.assertEqual(ipc.state, 'approved')
        ipc.action_paid()
        self.assertEqual(ipc.state, 'paid')

    def test_09_budget_workflow(self):
        Budget = self.env['construction.budget']
        budget = Budget.create({
            'project_id': self.project.id,
            'name': 'Test Budget',
            'budget_type': 'original',
        })
        self.assertEqual(budget.state, 'draft')
        budget.action_submit()
        self.assertEqual(budget.state, 'submitted')
        budget.action_approve()
        self.assertEqual(budget.state, 'approved')
        budget.action_freeze()
        self.assertEqual(budget.state, 'frozen')

    def test_10_project_financials(self):
        boq = self.Boq.create({
            'name': 'Financial BOQ',
            'code': 'BOQ-FIN',
            'project_id': self.project.id,
            'state': 'approved',
        })
        self.BoqItem.create({
            'boq_id': boq.id,
            'code': 'FIN.1',
            'name': 'Item 1',
            'unit': self.uom_unit.id,
            'quantity': 100.0,
            'rate': 1000.0,
        })
        self.project.invalidate_recordset(['project_value'])
        self.assertEqual(self.project.project_value, 100000.0)
