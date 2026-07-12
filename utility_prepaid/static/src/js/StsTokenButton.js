/** @odoo-module **/

import PosComponent from 'point_of_sale.PosComponent';
import ProductScreen from 'point_of_sale.ProductScreen';
import { useListener } from "@web/core/utils/hooks";
import Registries from 'point_of_sale.Registries';

export class StsTokenButton extends PosComponent {
    setup() {
        super.setup();
        useListener('click', this.onClick);
    }
    get currentOrder() {
        return this.env.pos.get_order();
    }
    async onClick() {
        const order = this.currentOrder;
        if (!order.get_partner()) {
            this.showPopup('ErrorPopup', {
                title: 'حدد العميل أولاً',
                body: 'يرجى اختيار العميل الذي تريد شحن عداده قبل بيع التوكن.',
            });
            return;
        }

        const partner = order.get_partner();
        // Get customer accounts loaded into pos
        const accounts = this.env.pos.utility_customer.filter(
            (c) => c.partner_id[0] === partner.id && c.payment_type === 'prepaid'
        );

        if (accounts.length === 0) {
            this.showPopup('ErrorPopup', {
                title: 'لا يوجد حساب مسبق الدفع',
                body: 'العميل المحدد ليس لديه أي حسابات بعدادات مسبقة الدفع.',
            });
            return;
        }

        const { confirmed, payload } = await this.showPopup('StsTokenPopup', {
            accounts: accounts,
        });

        if (confirmed) {
            const amount = payload.amount;
            const accountId = payload.accountId;
            const meterId = payload.meterId;

            // Find a dummy STS product or the first available product to hold the charge
            let product = this.env.pos.db.search_product_in_category(0, 'STS');
            if (product && product.length > 0) {
                product = product[0];
            } else {
                // fallback to any service product or just the first product
                const all_products = this.env.pos.db.get_product_by_category(0);
                product = all_products.length > 0 ? all_products[0] : null;
            }

            if (!product) {
                this.showPopup('ErrorPopup', {
                    title: 'لا يوجد منتج للتوكن',
                    body: 'يرجى تعريف منتج في النظام لبيع التوكن.',
                });
                return;
            }

            order.add_product(product, {
                price: amount,
                quantity: 1,
            });

            // Store utility info in the order (or current line) to be sent to backend
            order.utility_account_id = accountId;
            order.utility_meter_id = meterId;
            order.utility_amount = amount;
            
            // Optionally add a note to the line
            const currentLine = order.get_selected_orderline();
            if (currentLine) {
                currentLine.set_customer_note(`شحن حساب رقم: ${accounts.find(a => a.id === accountId).customer_number}`);
            }
        }
    }
}

StsTokenButton.template = 'utility_prepaid.StsTokenButton';

ProductScreen.addControlButton({
    component: StsTokenButton,
    condition: function () {
        return true;
    },
});

Registries.Component.add(StsTokenButton);
