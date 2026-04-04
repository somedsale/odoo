/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

function floatToParts(value) {
    if (value === false || value === null || value === undefined) {
        return { hour: "", minute: "" };
    }

    let hour = Math.floor(value);
    let minute = Math.round((value - hour) * 60);

    if (minute === 60) {
        hour += 1;
        minute = 0;
    }
    if (hour > 23) {
        hour = 23;
        minute = 59;
    }

    return {
        hour: String(hour).padStart(2, "0"),
        minute: String(minute).padStart(2, "0"),
    };
}

function partsToFloat(hour, minute) {
    const h = parseInt(hour || "0", 10);
    const m = parseInt(minute || "0", 10);
    return h + (m / 60);
}

export class TimeDropdownSplitField extends Component {
    static template = "overtime_request.TimeDropdownSplitField";
    static props = {
        ...standardFieldProps,
    };
    static supportedTypes = ["float"];

    get hours() {
        return Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));
    }

    get minutes() {
        return Array.from({ length: 60 }, (_, i) => String(i).padStart(2, "0"));
    }

    get currentParts() {
        return floatToParts(this.props.record.data[this.props.name]);
    }

    onHourChange(ev) {
        const hour = ev.target.value;
        const minute = this.currentParts.minute || "00";
        this.props.record.update({
            [this.props.name]: partsToFloat(hour, minute),
        });
    }

    onMinuteChange(ev) {
        const minute = ev.target.value;
        const hour = this.currentParts.hour || "00";
        this.props.record.update({
            [this.props.name]: partsToFloat(hour, minute),
        });
    }
}

registry.category("fields").add("time_dropdown_split", {
    component: TimeDropdownSplitField,
});