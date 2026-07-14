/** @odoo-module **/

import { registry } from '@web/core/registry';
import { PrepaidTokenPopup } from '@utility_prepaid/js/prepaid_token_popup';
import { PrepaidStatusPopup } from '@utility_prepaid/js/prepaid_status_popup';

registry.category('pos_popups').add('prepaid_token_popup', PrepaidTokenPopup);
registry.category('pos_popups').add('prepaid_status_popup', PrepaidStatusPopup);
