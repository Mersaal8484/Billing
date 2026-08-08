/** @odoo-module **/

import { registry } from "@odoo/core/registry";
import { Component, onMounted, onWillUpdateProps, useRef } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class UtilityMediaImageField extends Component {
    setup() {
        this.containerRef = useRef("container");
        const render = () => {
            const node = this.containerRef.el;
            if (!node) {
                return;
            }
            const value = this.props.value || "";
            if (value) {
                node.innerHTML = `<img src="${value}" alt="${this.props.name || ""}" class="img-fluid rounded border shadow-sm" style="max-width:100%; max-height:320px; object-fit:contain;" />`;
            } else {
                node.innerHTML = `<div class="text-center text-muted py-5 px-3 border rounded bg-light"><i class="fa fa-image fa-3x mb-2 opacity-50"></i><div>لا توجد صورة متاحة</div></div>`;
            }
        };
        onMounted(render);
        onWillUpdateProps(render);
    }
}

UtilityMediaImageField.template = "utility_billing.UtilityMediaImageField";
UtilityMediaImageField.supportedTypes = ["char"];
UtilityMediaImageField.props = standardFieldProps;

registry.category("fields").add("utility_media_image", UtilityMediaImageField);
