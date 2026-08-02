"""Enlarge utility sequence paddings and add the private-transformer sequence.

All ir.sequence records are noupdate=1 data, so changing the XML padding is
not enough for existing databases: this migration updates the records that
are already installed and creates the missing sequences.
"""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1) Enlarge every utility.* sequence to 9 digits so customer-heavy
    #    databases never run out of numbers (was 5 or 6).
    sequences = env['ir.sequence'].search([
        ('code', 'like', 'utility.%'),
        ('padding', '<', 9),
    ])
    if sequences:
        sequences.write({'padding': 9})

    # 2) Create the private-transformer sequence (used when is_private=True)
    if not env['ir.sequence'].search([('code', '=', 'utility.transformer.private')]):
        env['ir.sequence'].create({
            'name': 'تسلسل المحولات الخاصة',
            'code': 'utility.transformer.private',
            'prefix': 'PRV/%(year)s/',
            'padding': 9,
            'company_id': False,
        })

    # 3) Create the general transformer sequence (available for normal transformers)
    if not env['ir.sequence'].search([('code', '=', 'utility.transformer')]):
        env['ir.sequence'].create({
            'name': 'تسلسل أرقام المحولات',
            'code': 'utility.transformer',
            'prefix': 'TRF/%(year)s/',
            'padding': 9,
            'company_id': False,
        })
