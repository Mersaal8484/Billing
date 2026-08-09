"""Repair dedicated partner identity data after the accounting-partner split."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
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
