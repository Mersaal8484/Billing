"""Enlarge sequence paddings and add the transformer sequences (code-only).

All ir.sequence records are noupdate=1 XML data, so changing the data files
would not affect existing databases. This migration (plus the post_init_hook
for fresh installs) is the single source of truth for the sequence sizing:

* every utility.* sequence and the standard document sequences used by the
  utility apps (sale.order bills, recurring invoices, POS sales) grow to
  9 digits because they scale with the customer count;
* the private transformer gets its own dedicated sequence (PRV/...),
  fully separated from the regular transformer sequence (TRF/...).
"""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    # 1) Enlarge sequences (idempotent).
    cr.execute(
        """
        UPDATE ir_sequence
        SET padding = 9
        WHERE (
            code LIKE 'utility.%%'
            OR code IN (
                'sale.order',
                'recurring.payment',
                'pos.order',
                'pos.order.line',
                'pos.session'
            )
        )
          AND padding < 9
        """
    )

    # 2) Create the transformer sequences (regular + private) if missing.
    env = api.Environment(cr, SUPERUSER_ID, {})
    Sequence = env['ir.sequence']
    specs = (
        ('utility.transformer', 'تسلسل أرقام المحولات', 'TRF/%(year)s/'),
        ('utility.transformer.private', 'تسلسل المحولات الخاصة', 'PRV/%(year)s/'),
    )
    for code, name, prefix in specs:
        if Sequence.search([('code', '=', code)]):
            continue
        Sequence.create({
            'name': name,
            'code': code,
            'prefix': prefix,
            'padding': 9,
            'company_id': False,
        })
