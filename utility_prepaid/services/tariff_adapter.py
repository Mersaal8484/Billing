import logging
import math
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TariffAdapter:
    """Adapter for tariff calculations across different pricing models.

    Supports flat, tiered, block, seasonal, and time-of-use (TOU) tariffs
    with subsidy and tax handling. All calculations are pure Python and
    receive Odoo records as parameters.
    """

    def __init__(self, env):
        """Initialize with an Odoo environment.

        Args:
            env: Odoo environment.
        """
        self.env = env

    def get_tariff_for_account(self, account):
        """Get the applicable tariff for a customer account.

        Resolves tariff from the account's contract template or category.

        Args:
            account: utility.customer record.

        Returns:
            tariff record or price_per_kwh float from contract template.
        """
        if not account:
            raise UserError("Account is required to determine tariff.")

        if account.contract_template_id:
            template = account.contract_template_id
            if hasattr(template, 'tariff_id') and template.tariff_id:
                return template.tariff_id
            return template.price_per_kwh

        if account.category_id:
            category_tariff = self.env['utility.tariff'].search([
                ('category_ids', 'in', account.category_id.id),
                ('active', '=', True),
                ('company_id', '=', account.company_id.id),
            ], limit=1)
            if category_tariff:
                return category_tariff

        return None

    def calculate_energy_kwh(self, amount, tariff, date=None):
        """Calculate kWh based on amount and tariff configuration.

        Dispatches to the appropriate calculation method based on
        tariff type.

        Args:
            amount: net energy amount (after service charges and taxes).
            tariff: tariff record or price_per_kwh float.
            date: optional date for seasonal tariff lookup.

        Returns:
            float: kWh that the amount purchases.
        """
        if not amount or amount <= 0:
            return 0.0
        if not tariff:
            raise UserError("Tariff is required for kWh calculation.")

        if isinstance(tariff, (int, float)):
            return amount / tariff if tariff else 0.0

        tariff_type = getattr(tariff, 'tariff_type', 'flat')
        if tariff_type == 'flat':
            price = getattr(tariff, 'price_per_kwh', 0)
            service = getattr(tariff, 'service_charge', 0)
            return self.calculate_flat_tariff(amount, price, service)
        elif tariff_type == 'tiered':
            blocks = getattr(tariff, 'tier_ids', [])
            return self.calculate_tiered_tariff(amount, blocks)
        elif tariff_type == 'block':
            blocks = getattr(tariff, 'block_ids', [])
            return self.calculate_block_tariff(amount, blocks)
        elif tariff_type == 'seasonal':
            return self.calculate_seasonal_tariff(amount, tariff, date)
        elif tariff_type == 'tou':
            return self.calculate_tou_tariff(amount, tariff)
        else:
            price = getattr(tariff, 'price_per_kwh', 0)
            return amount / price if price else 0.0

    def calculate_flat_tariff(self, amount, price_per_kwh, service_charge=0):
        """Simple flat tariff calculation.

        Args:
            amount: net energy amount available for kWh purchase.
            price_per_kwh: price per kWh.
            service_charge: fixed service charge (already deducted from amount).

        Returns:
            float: kWh purchased.
        """
        if not price_per_kwh or price_per_kwh <= 0:
            return 0.0
        net_amount = max(0, amount - service_charge)
        return net_amount / price_per_kwh

    def calculate_tiered_tariff(self, amount, tariff_blocks):
        """Calculate kWh using tiered (slab) pricing.

        Each tier has a consumption range and a price. The amount is
        consumed tier by tier from cheapest to most expensive.

        Args:
            amount: net energy amount.
            tariff_blocks: list of dicts with keys:
                - min_kwh: start of tier
                - max_kwh: end of tier (None for unlimited)
                - price_per_kwh: price for this tier

        Returns:
            float: total kWh purchased.
        """
        if not tariff_blocks:
            return 0.0

        remaining = amount
        total_kwh = 0.0
        sorted_blocks = sorted(tariff_blocks, key=lambda b: b.get('price_per_kwh', 0))

        for block in sorted_blocks:
            if remaining <= 0:
                break
            price = block.get('price_per_kwh', 0)
            if price <= 0:
                continue

            min_kwh = block.get('min_kwh', 0)
            max_kwh = block.get('max_kwh')

            if max_kwh is not None:
                tier_size = max_kwh - min_kwh
                tier_cost = tier_size * price
                if remaining >= tier_cost:
                    total_kwh += tier_size
                    remaining -= tier_cost
                else:
                    total_kwh += remaining / price
                    remaining = 0
            else:
                total_kwh += remaining / price
                remaining = 0

        return total_kwh

    def calculate_block_tariff(self, amount, tariff_blocks):
        """Calculate kWh using block (increasing slab) pricing.

        Unlike tiered, block pricing applies sequentially: first block
        is consumed first, then second, etc., regardless of price.

        Args:
            amount: net energy amount.
            tariff_blocks: list of dicts with keys:
                - sequence: block order
                - max_kwh: maximum kWh in this block
                - price_per_kwh: price for this block

        Returns:
            float: total kWh purchased.
        """
        if not tariff_blocks:
            return 0.0

        remaining = amount
        total_kwh = 0.0
        sorted_blocks = sorted(tariff_blocks, key=lambda b: b.get('sequence', 0))

        for block in sorted_blocks:
            if remaining <= 0:
                break
            price = block.get('price_per_kwh', 0)
            max_kwh = block.get('max_kwh', 0)
            if price <= 0 or max_kwh <= 0:
                continue

            block_cost = max_kwh * price
            if remaining >= block_cost:
                total_kwh += max_kwh
                remaining -= block_cost
            else:
                total_kwh += remaining / price
                remaining = 0

        return total_kwh

    def calculate_seasonal_tariff(self, amount, tariff, date=None):
        """Calculate kWh using seasonal tariff rates.

        Selects the appropriate rate based on the date's season.

        Args:
            amount: net energy amount.
            tariff: tariff record with seasonal rates.
            date: date to determine season (defaults to today).

        Returns:
            float: kWh purchased.
        """
        if not tariff:
            return 0.0

        date = date or datetime.today().date()
        month = date.month

        if hasattr(tariff, 'summer_price') and hasattr(tariff, 'winter_price'):
            if hasattr(tariff, 'seasonal_months'):
                summer_months = tariff.seasonal_months or [6, 7, 8, 9]
                is_summer = month in summer_months
            else:
                is_summer = month in (6, 7, 8, 9)

            price = tariff.summer_price if is_summer else tariff.winter_price
        else:
            price = getattr(tariff, 'price_per_kwh', 0)

        return amount / price if price else 0.0

    def calculate_tou_tariff(self, amount, tariff, time_of_use=None):
        """Calculate kWh using time-of-use pricing.

        Applies different rates based on peak/off-peak hours.

        Args:
            amount: net energy amount.
            tariff: tariff record with TOU rates.
            time_of_use: optional hour (0-23) or 'peak'/'off_peak'.

        Returns:
            float: kWh purchased.
        """
        if not tariff:
            return 0.0

        if time_of_use is None:
            time_of_use = datetime.now().hour

        if isinstance(time_of_use, str):
            period = time_of_use
        elif isinstance(time_of_use, int):
            peak_start = getattr(tariff, 'peak_start_hour', 8)
            peak_end = getattr(tariff, 'peak_end_hour', 22)
            period = 'peak' if peak_start <= time_of_use < peak_end else 'off_peak'
        else:
            period = 'off_peak'

        if period == 'peak':
            price = getattr(tariff, 'peak_price', 0) or getattr(tariff, 'price_per_kwh', 0)
        else:
            price = getattr(tariff, 'off_peak_price', 0) or getattr(tariff, 'price_per_kwh', 0)

        return amount / price if price else 0.0

    def apply_subsidy(self, amount, subscriber, tariff):
        """Apply subsidized pricing for eligible subscribers.

        Args:
            amount: original energy amount.
            subscriber: utility.subscriber record or subscriber type.
            tariff: tariff record.

        Returns:
            float: subsidized amount (lower than original if eligible).
        """
        if not subscriber or not tariff:
            return amount

        subsidy_pct = getattr(subscriber, 'subsidy_percentage', 0)
        if hasattr(tariff, 'subsidy_percentage') and tariff.subsidy_percentage:
            subsidy_pct = tariff.subsidy_percentage

        if subsidy_pct <= 0:
            return amount

        subsidized = amount * (1 - subsidy_pct / 100.0)
        _logger.debug(
            "Subsidy applied: %s%% off %s = %s",
            subsidy_pct, amount, subsidized,
        )
        return subsidized

    def apply_tax(self, amount, tax_rate):
        """Calculate tax on an amount.

        Args:
            amount: pre-tax amount.
            tax_rate: tax percentage.

        Returns:
            float: tax amount.
        """
        if not tax_rate or tax_rate <= 0:
            return 0.0
        return amount * (tax_rate / 100.0)

    def round_amount(self, amount, rounding_method='half-up'):
        """Round an amount using the specified method.

        Args:
            amount: float to round.
            rounding_method: 'half-up', 'down', 'up', or 'nearest'.

        Returns:
            float: rounded amount.
        """
        if amount is None:
            return 0.0

        decimal_amount = Decimal(str(amount))

        if rounding_method == 'half-up':
            rounded = decimal_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        elif rounding_method == 'down':
            rounded = decimal_amount.quantize(Decimal('0.01'), rounding=math.floor)
        elif rounding_method == 'up':
            rounded = decimal_amount.quantize(Decimal('0.01'), rounding=math.ceil)
        elif rounding_method == 'nearest':
            rounded = decimal_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            rounded = decimal_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return float(rounded)
