/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

function floatToTimeString(value) {
    if (value === false || value === null || value === undefined) {
        return "";
    }

    let hours = Math.floor(value);
    let minutes = Math.round((value - hours) * 60);

    if (minutes === 60) {
        hours += 1;
        minutes = 0;
    }
    if (hours >= 24) {
        hours = 23;
        minutes = 59;
    }

    const hh = String(hours).padStart(2, "0");
    const mm = String(minutes).padStart(2, "0");
    return `${hh}:${mm}`;
}

function timeStringToFloat(value) {
    if (!value) {
        return 0;
    }
    const [hh, mm] = value.split(":").map(Number);
    return (hh || 0) + ((mm || 0) / 60);
}

export class TimeDropdown24hField extends Component {
    static template = "overtime_request.TimeDropdown24hField";
    static props = {
        ...standardFieldProps,
    };
    static supportedTypes = ["float"];

    setup() {
        this.state = useState({
            options: this._buildTimeOptions(),
        });
    }

    _buildTimeOptions() {
        const result = [];
        for (let hour = 0; hour < 24; hour++) {
            for (let minute = 0; minute < 60; minute++) {
                const hh = String(hour).padStart(2, "0");
                const mm = String(minute).padStart(2, "0");
                const label = `${hh}:${mm}`;
                result.push({
                    value: label,
                    label: label,
                });
            }
        }
        return result;
    }

    get currentValue() {
        return floatToTimeString(this.props.record.data[this.props.name]);
    }

    onChange(ev) {
        const value = ev.target.value;
        this.props.record.update({
            [this.props.name]: timeStringToFloat(value),
        });
    }
}

registry.category("fields").add("time_dropdown_24h", {
    component: TimeDropdown24hField,
});