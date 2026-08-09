"""Repair dedicated partner identity data after the accounting-partner split."""

import logging


_logger = logging.getLogger(__name__)


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
        """,
        [table_name, column_name],
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    # Finish the split for legacy singleton accounts too. Shared partners were
    # handled by the previous migration, but singleton accounts must also get
    # a dedicated accounting partner for one consistent data model.
    cr.execute(
        """
        SELECT id, partner_id, customer_number
          FROM utility_customer
         WHERE owner_partner_id = partner_id
           AND partner_id IS NOT NULL
         ORDER BY id
        """
    )
    singleton_accounts = cr.fetchall()
    for customer_id, owner_id, customer_number in singleton_accounts:
        columns = [
            'mobile', 'phone', 'street', 'street2', 'city', 'zip', 'email',
            'vat', 'lang', 'country_id', 'state_id', 'region_id', 'area_id',
            'zone_id', 'company_id', 'national_id', 'register_number',
        ]
        columns = [c for c in columns if _column_exists(cr, 'res_partner', c)]
        target_columns = [
            'name', 'active', 'is_company', 'customer_rank', 'parent_id',
        ] + columns + ['is_subscriber', 'create_uid', 'create_date', 'write_uid', 'write_date']
        source_expressions = [
            "COALESCE(name, '') || ' - حساب كهرباء ' || %s",
            'active', 'is_company', 'GREATEST(customer_rank, 1)', 'NULL',
        ] + columns + ['TRUE', '%s', 'NOW()', '%s', 'NOW()']
        cr.execute(
            'INSERT INTO res_partner (%s) SELECT %s FROM res_partner '
            'WHERE id = %%s RETURNING id' % (
                ', '.join(target_columns), ', '.join(source_expressions)),
            [customer_number, 1, 1, owner_id],
        )
        dedicated_id = cr.fetchone()[0]
        cr.execute(
            "UPDATE utility_customer SET partner_id = %s WHERE id = %s",
            [dedicated_id, customer_id],
        )
        _logger.info(
            'Created dedicated accounting partner %s for legacy customer %s.',
            dedicated_id, customer_id,
        )

    # Keep the legal owner's contact and routing data available on the
    # dedicated accounting contact. Financial owner fields are deliberately
    # cleared because their allocation to multiple accounts is ambiguous.
    cr.execute(
        """
        UPDATE res_partner account_partner
           SET mobile = owner.mobile,
               phone = owner.phone,
               street = owner.street,
               street2 = owner.street2,
               city = owner.city,
               zip = owner.zip,
               email = owner.email,
               vat = owner.vat,
               country_id = owner.country_id,
               state_id = owner.state_id,
               region_id = owner.region_id,
               area_id = owner.area_id,
               zone_id = owner.zone_id,
               open_balance = 0,
               pec_credit = 0,
               is_credit_raised = FALSE,
               credit_raise_date = NULL
          FROM utility_customer customer
          JOIN res_partner owner ON owner.id = customer.owner_partner_id
         WHERE account_partner.id = customer.partner_id
           AND customer.owner_partner_id IS NOT NULL
           AND customer.partner_id <> customer.owner_partner_id
        """
    )
    _logger.info('Utility accounting partner identity migration completed.')
