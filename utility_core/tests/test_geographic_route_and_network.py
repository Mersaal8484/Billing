from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestGeographicRouteAndNetwork(TransactionCase):
    """Deterministic tests for the shared route hierarchy and network types."""

    def setUp(self):
        super().setUp()
        self.Customer = self.env['utility.customer']
        self.Region = self.env['utility.region']
        self.Transformer = self.env['utility.transformer']
        self.Feeder = self.env['utility.feeder']

    def test_route_domain_specificity(self):
        self.assertEqual(
            self.Customer._get_route_domain(1, 2, 3), [('zone_id', '=', 3)])
        self.assertEqual(
            self.Customer._get_route_domain(1, 2), [('area_id', '=', 2)])
        self.assertEqual(
            self.Customer._get_route_domain(1), [('region_id', '=', 1)])
        self.assertEqual(self.Customer._get_route_domain(), [])

    def test_private_transformer_is_geographically_validated(self):
        region = self.Region.create({'name': 'منطقة اختبار', 'code': 'GEO-R', 'type': 'region'})
        area = self.Region.create({'name': 'فرع اختبار', 'code': 'GEO-A', 'type': 'area', 'parent_id': region.id})
        zone = self.Region.create({'name': 'ناحية اختبار', 'code': 'GEO-Z', 'type': 'zone', 'parent_id': area.id})
        other_region = self.Region.create({'name': 'منطقة أخرى', 'code': 'GEO-R2', 'type': 'region'})
        other_area = self.Region.create({'name': 'فرع آخر', 'code': 'GEO-A2', 'type': 'area', 'parent_id': other_region.id})
        other_zone = self.Region.create({'name': 'ناحية أخرى', 'code': 'GEO-Z2', 'type': 'zone', 'parent_id': other_area.id})
        transformer = self.Transformer.create({
            'name': 'محول خاص اختبار', 'code': 'GEO-T', 'is_private': True,
            'zone_region_id': zone.id,
        })
        zone.write({'private_transformer_id': transformer.id})
        self.assertEqual(zone.private_transformer_id, transformer)
        with self.assertRaises(ValidationError):
            other_zone.write({'private_transformer_id': transformer.id})

    def test_transformer_and_zone_have_a_bidirectional_one_to_one_link(self):
        region = self.Region.create({'name': 'منطقة 1:1', 'code': 'ONE-R', 'type': 'region'})
        area = self.Region.create({'name': 'فرع 1:1', 'code': 'ONE-A', 'type': 'area', 'parent_id': region.id})
        zone = self.Region.create({'name': 'Zone 1:1', 'code': 'ONE-Z', 'type': 'zone', 'parent_id': area.id})
        other_zone = self.Region.create({'name': 'Zone 1:1 آخر', 'code': 'ONE-Z2', 'type': 'zone', 'parent_id': area.id})

        transformer = self.Transformer.create({
            'name': 'محول 1:1', 'code': 'ONE-T', 'zone_region_id': zone.id,
        })

        self.assertEqual(transformer.zone_region_id, zone)
        self.assertEqual(zone.transformer_origin_id, transformer)
        with self.assertRaises(ValidationError):
            self.Transformer.create({
                'name': 'محول مكرر', 'code': 'ONE-T2', 'zone_region_id': zone.id,
            })

        transformer.write({'zone_region_id': other_zone.id})
        self.assertFalse(zone.transformer_origin_id)
        self.assertEqual(other_zone.transformer_origin_id, transformer)

    def test_feeder_type_is_backward_compatible_and_searchable(self):
        default_feeder = self.Feeder.create({'name': 'فيدر توزيع', 'code': 'GEO-F1'})
        production = self.Feeder.create({
            'name': 'فيدر إنتاج', 'code': 'GEO-F2', 'feeder_type': 'production_area',
        })
        self.assertEqual(default_feeder.feeder_type, 'distribution')
        self.assertEqual(production.feeder_type, 'production_area')
        self.assertIn(production, self.Feeder.search([('feeder_type', '=', 'production_area')]))
