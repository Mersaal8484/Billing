/** @odoo-module **/

import { registry } from "@web/core/registry";
import { CharField } from "@web/views/fields/char/char_field";

export class UtilityMediaImageField extends CharField {}

UtilityMediaImageField.template = "utility_billing.UtilityMediaImageField";
UtilityMediaImageField.supportedTypes = ["char"];
UtilityMediaImageField.props = CharField.props;

registry.category("fields").add("utility_media_image", UtilityMediaImageField);
