/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class TimePickerFloatField extends Component {
    static template = "overtime_request.TimePickerFloatField";
    static props = {
        ...standardFieldProps,
    };
    static supportedTypes = ["float"];

    get formattedValue() {
        const value = this.props.record.data[this.props.name];
        if (value === false || value === null || value === undefined) {
            return "";
        }

        let hours = Math.floor(value);
        let minutes = Math.round((value - hours) * 60);

        if (minutes === 60) {
            hours += 1;
            minutes = 0;
        }

        const hh = String(hours).padStart(2, "0");
        const mm = String(minutes).padStart(2, "0");
        return `${hh}:${mm}`;
    }

    onInput(ev) {
        const value = ev.target.value;
        if (!value) {
            this.props.record.update({ [this.props.name]: 0 });
            return;
        }

        const [hh, mm] = value.split(":").map(Number);
        const floatValue = (hh || 0) + ((mm || 0) / 60);
        this.props.record.update({ [this.props.name]: floatValue });
    }
}

registry.category("fields").add("time_picker_float", {
    component: TimePickerFloatField,
});