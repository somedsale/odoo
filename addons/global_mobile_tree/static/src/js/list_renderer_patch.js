/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.__mobileBreakpoint = 768;
    },

    get isRelationalList() {
        return !!this.props.list?.model?.config?.isRelational;
    },

    get isEditableList() {
        return !!this.props.archInfo?.editable;
    },

    get isGroupedList() {
        return !!this.props.list?.groups?.length || !!this.props.list?.isGrouped;
    },

    get shouldUseMobileCards() {
        const isSmall = window.innerWidth <= this.__mobileBreakpoint;
        return isSmall
            && !this.isEditableList
            && !this.isRelationalList
            && !this.isGroupedList;
    },

    getGlobalVisibleColumns(record) {
        const cols = this.columns || this.props.columns || this.props.archInfo?.columns || [];
        return cols.filter((col) => {
            return col
                && col.name
                && (!col.type || col.type === "field")
                && col.optional !== "hide";
        });
    },

    getGlobalColumnLabel(column) {
        return column.string || column.name || "";
    },

    getGlobalFieldValue(record, column) {
        const value = record?.data?.[column.name];

        if (value === undefined || value === null || value === false) {
            return "";
        }
        if (Array.isArray(value) && value.length >= 2) {
            return value[1] || "";
        }
        if (Array.isArray(value)) {
            return value.join(", ");
        }
        if (typeof value === "boolean") {
            return value ? "Yes" : "No";
        }
        if (typeof value === "object") {
            return value.display_name || "";
        }
        return String(value);
    },

    openGlobalRecord(record) {
        if (this.props.openRecord) {
            this.props.openRecord(record);
        }
    },
});