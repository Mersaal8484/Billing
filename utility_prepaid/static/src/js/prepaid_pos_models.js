/** @odoo-module **/

import { Order, Orderline } from '@point_of_sale/app/models/pos_order';
import { patch } from '@web/core/utils/patch';

patch(Order.prototype, {
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.utility_account_id = this.utility_account_id || false;
        json.utility_meter_id = this.utility_meter_id || false;
        json.utility_amount = this.utility_amount || 0;
        json.utility_kwh = this.utility_kwh || 0;
        json.utility_template_id = this.utility_template_id || false;
        json.is_prepaid_vending = this.is_prepaid_vending || false;
        json.utility_vending_quote = this.utility_vending_quote || null;
        return json;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.utility_account_id = json.utility_account_id || false;
        this.utility_meter_id = json.utility_meter_id || false;
        this.utility_amount = json.utility_amount || 0;
        this.utility_kwh = json.utility_kwh || 0;
        this.utility_template_id = json.utility_template_id || false;
        this.is_prepaid_vending = json.is_prepaid_vending || false;
        this.utility_vending_quote = json.utility_vending_quote || null;
    },

    set_prepaid_metadata(accountId, meterId, amount, kwh, templateId, quote) {
        this.utility_account_id = accountId;
        this.utility_meter_id = meterId;
        this.utility_amount = amount;
        this.utility_kwh = kwh;
        this.utility_template_id = templateId;
        this.utility_vending_quote = quote;
        this.is_prepaid_vending = true;
    },

    clear_prepaid_metadata() {
        this.utility_account_id = false;
        this.utility_meter_id = false;
        this.utility_amount = 0;
        this.utility_kwh = 0;
        this.utility_template_id = false;
        this.utility_vending_quote = null;
        this.is_prepaid_vending = false;
    },
});

patch(Orderline.prototype, {
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.is_prepaid_line = this.is_prepaid_line || false;
        return json;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.is_prepaid_line = json.is_prepaid_line || false;
    },
});
