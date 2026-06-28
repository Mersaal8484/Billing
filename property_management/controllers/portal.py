from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class PropertyCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'lease_count' in counters:
            tenant = request.env['property.tenant'].sudo().search([('partner_id', '=', partner.id)], limit=1)
            lease_count = request.env['property.lease'].sudo().search_count([('tenant_id', '=', tenant.id)]) if tenant else 0
            values['lease_count'] = lease_count

        if 'maintenance_count' in counters:
            tenant = request.env['property.tenant'].sudo().search([('partner_id', '=', partner.id)], limit=1)
            maintenance_count = request.env['property.maintenance'].sudo().search_count([('tenant_id', '=', tenant.id)]) if tenant else 0
            values['maintenance_count'] = maintenance_count

        if 'property_count' in counters:
            owner = request.env['property.owner'].sudo().search([('partner_id', '=', partner.id)], limit=1)
            property_count = request.env['property.property'].sudo().search_count([('owner_id', '=', owner.id)]) if owner else 0
            values['property_count'] = property_count

        return values

    @http.route(['/my/leases', '/my/leases/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_leases(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        tenant = request.env['property.tenant'].sudo().search([('partner_id', '=', partner.id)], limit=1)

        domain = [('tenant_id', '=', tenant.id)] if tenant else [('id', '=', 0)]
        
        lease_count = request.env['property.lease'].sudo().search_count(domain)
        pager = portal_pager(
            url="/my/leases",
            total=lease_count,
            page=page,
            step=10
        )
        
        leases = request.env['property.lease'].sudo().search(domain, limit=10, offset=pager['offset'])
        
        values.update({
            'leases': leases,
            'page_name': 'lease',
            'pager': pager,
            'default_url': '/my/leases',
        })
        return request.render("property_management.portal_my_leases", values)

    @http.route(['/my/leases/<int:lease_id>'], type='http', auth="user", website=True)
    def portal_my_lease_detail(self, lease_id, **kw):
        lease = request.env['property.lease'].sudo().browse(lease_id)
        partner = request.env.user.partner_id
        tenant = request.env['property.tenant'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        
        if not tenant or lease.tenant_id.id != tenant.id:
            return request.redirect('/my')
            
        values = self._prepare_portal_layout_values()
        values.update({
            'lease': lease,
            'page_name': 'lease',
        })
        return request.render("property_management.portal_my_lease_detail", values)

    @http.route(['/my/maintenance', '/my/maintenance/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_maintenance(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        tenant = request.env['property.tenant'].sudo().search([('partner_id', '=', partner.id)], limit=1)

        domain = [('tenant_id', '=', tenant.id)] if tenant else [('id', '=', 0)]
        
        maintenance_count = request.env['property.maintenance'].sudo().search_count(domain)
        pager = portal_pager(
            url="/my/maintenance",
            total=maintenance_count,
            page=page,
            step=10
        )
        
        maintenance_requests = request.env['property.maintenance'].sudo().search(domain, limit=10, offset=pager['offset'])
        
        values.update({
            'maintenance_requests': maintenance_requests,
            'page_name': 'maintenance',
            'pager': pager,
            'default_url': '/my/maintenance',
        })
        return request.render("property_management.portal_my_maintenance", values)

    @http.route(['/my/maintenance/<int:maintenance_id>'], type='http', auth="user", website=True)
    def portal_my_maintenance_detail(self, maintenance_id, **kw):
        maintenance = request.env['property.maintenance'].sudo().browse(maintenance_id)
        partner = request.env.user.partner_id
        tenant = request.env['property.tenant'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        
        if not tenant or maintenance.tenant_id.id != tenant.id:
            return request.redirect('/my')
            
        values = self._prepare_portal_layout_values()
        values.update({
            'maintenance': maintenance,
            'page_name': 'maintenance',
        })
        return request.render("property_management.portal_my_maintenance_detail", values)

    @http.route(['/my/maintenance/new'], type='http', auth="user", website=True)
    def portal_my_maintenance_new(self, **kw):
        partner = request.env.user.partner_id
        tenant = request.env['property.tenant'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        if not tenant:
            return request.redirect('/my')
            
        if request.httprequest.method == 'POST':
            unit_id = int(request.params.get('unit_id', 0))
            maintenance_type_id = int(request.params.get('maintenance_type_id', 0))
            description = request.params.get('description', '')
            priority = request.params.get('priority', 'normal')
            
            unit = request.env['property.unit'].sudo().browse(unit_id)
            if unit and maintenance_type_id and description:
                new_req = request.env['property.maintenance'].sudo().create({
                    'property_id': unit.property_id.id,
                    'building_id': unit.building_id.id,
                    'unit_id': unit.id,
                    'tenant_id': tenant.id,
                    'maintenance_type': maintenance_type_id,
                    'priority': priority,
                    'description': description,
                    'state': 'submitted',
                })
                return request.redirect(f'/my/maintenance/{new_req.id}')
                
        leases = request.env['property.lease'].sudo().search([('tenant_id', '=', tenant.id), ('state', '=', 'active')])
        units = leases.mapped('unit_id')
        maintenance_types = request.env['property.maintenance.type'].sudo().search([])
        
        values = self._prepare_portal_layout_values()
        values.update({
            'units': units,
            'maintenance_types': maintenance_types,
            'page_name': 'maintenance',
        })
        return request.render("property_management.portal_my_maintenance_new", values)

    @http.route(['/my/properties', '/my/properties/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_properties(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        owner = request.env['property.owner'].sudo().search([('partner_id', '=', partner.id)], limit=1)

        domain = [('owner_id', '=', owner.id)] if owner else [('id', '=', 0)]
        
        property_count = request.env['property.property'].sudo().search_count(domain)
        pager = portal_pager(
            url="/my/properties",
            total=property_count,
            page=page,
            step=10
        )
        
        properties = request.env['property.property'].sudo().search(domain, limit=10, offset=pager['offset'])
        
        values.update({
            'properties': properties,
            'owner': owner,
            'page_name': 'property',
            'pager': pager,
            'default_url': '/my/properties',
        })
        return request.render("property_management.portal_my_properties", values)
