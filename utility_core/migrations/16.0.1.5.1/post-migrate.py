import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    if not version:
        return
    
    _logger.info('Migrating supervisor_id to user_ids in utility.route...')
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # We use with_context(active_test=False) just in case some routes are archived
    routes = env['utility.route'].with_context(active_test=False).search([('supervisor_id', '!=', False)])
    if routes:
        _logger.info(f'Found {len(routes)} routes with supervisor_id. Migrating...')
        count = 0
        for route in routes:
            if route.supervisor_id.id not in route.user_ids.ids:
                route.write({'user_ids': [(4, route.supervisor_id.id)]})
                count += 1
        _logger.info(f'Successfully migrated {count} supervisors to user_ids.')
    else:
        _logger.info('No routes found with supervisor_id. Nothing to migrate.')
