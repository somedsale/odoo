/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";
import { useSortable } from "@web/core/utils/sortable_owl";
import { ListRenderer } from "@web/views/list/list_renderer";

const COLUMN_ORDER_PREFIX = "column_reorder_tspl.columns,";

function getColumnKey(column) {
    return String(column.id || column.name || "");
}

function createColumnOrderKey(renderer) {
    let keyParts = {
        fields: renderer.props.list.fieldNames,
        model: renderer.props.list.resModel,
        viewMode: "list",
        viewId: renderer.env.config.viewId,
    };

    if (renderer.props.nestedKeyOptionalFieldsData) {
        keyParts = Object.assign(keyParts, {
            model: renderer.props.nestedKeyOptionalFieldsData.model,
            viewMode: renderer.props.nestedKeyOptionalFieldsData.viewMode,
            relationalField: renderer.props.nestedKeyOptionalFieldsData.field,
            subViewType: "list",
        });
    }

    const parts = ["model", "viewMode", "viewId", "relationalField", "subViewType"];
    const viewIdentifier = [COLUMN_ORDER_PREFIX.slice(0, -1)];
    for (const partName of parts) {
        if (partName in keyParts) {
            viewIdentifier.push(keyParts[partName]);
        }
    }
    for (const fieldName of [...keyParts.fields].sort((left, right) => (left < right ? -1 : 1))) {
        viewIdentifier.push(fieldName);
    }
    return viewIdentifier.join(",");
}

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.keyColumnOrder = createColumnOrderKey(this);
        this.columnOrder = this.loadColumnOrder();
        this.state.columns = this.getActiveColumns(this.props.list);

        useSortable({
            enable: () =>
                !this.uiService.isSmall &&
                !this.editedRecord &&
                this.state.columns.filter((column) => column.type === "field" && column.hasLabel)
                    .length > 1,
            ref: this.rootRef,
            elements: ".o_column_reorder_header",
            handle: ".o_column_reorder_handle",
            cursor: "grabbing",
            onDragStart: () => {
                this.preventReorder = true;
            },
            onDrop: ({ element, previous, next }) => {
                this.onColumnReorderDrop(element, previous, next);
            },
        });
    },

    getActiveColumns(list) {
        const columns = super.getActiveColumns(list);
        return this.sortColumnsBySavedOrder(columns);
    },

    loadColumnOrder() {
        const rawOrder = browser.localStorage.getItem(this.keyColumnOrder);
        if (!rawOrder) {
            return [];
        }
        try {
            return JSON.parse(rawOrder);
        } catch {
            browser.localStorage.removeItem(this.keyColumnOrder);
            return [];
        }
    },

    saveColumnOrder() {
        if (!this.columnOrder.length) {
            browser.localStorage.removeItem(this.keyColumnOrder);
            return;
        }
        browser.localStorage.setItem(this.keyColumnOrder, JSON.stringify(this.columnOrder));
    },

    getNormalizedColumnOrder(columns) {
        if (!columns || !Array.isArray(columns)) {
            return [];
        }
        const currentOrder = columns.map(getColumnKey);
        const savedOrder = this.columnOrder.filter((columnId) => currentOrder.includes(columnId));
        return [...savedOrder, ...currentOrder.filter((columnId) => !savedOrder.includes(columnId))];
    },

    sortColumnsBySavedOrder(columns) {
        if (!columns || !Array.isArray(columns) || !this.columnOrder || !this.columnOrder.length) {
            return columns;
        }
        const orderIndex = new Map(
            this.getNormalizedColumnOrder(columns).map((columnId, index) => [columnId, index])
        );
        return [...columns].sort((left, right) => {
            const leftIndex = orderIndex.get(getColumnKey(left)) ?? Number.MAX_SAFE_INTEGER;
            const rightIndex = orderIndex.get(getColumnKey(right)) ?? Number.MAX_SAFE_INTEGER;
            return leftIndex - rightIndex;
        });
    },

    onColumnReorderDrop(element, previous, next) {
        const movedId = element?.dataset?.columnId;
        if (!movedId) {
            return;
        }

        const order = this.getNormalizedColumnOrder(this.state.columns).filter((columnId) => columnId !== movedId);
        const previousId = previous?.dataset?.columnId;
        const nextId = next?.dataset?.columnId;

        let targetIndex = order.length;
        if (nextId) {
            targetIndex = order.indexOf(nextId);
        } else if (previousId) {
            targetIndex = order.indexOf(previousId) + 1;
        }

        if (targetIndex < 0) {
            targetIndex = order.length;
        }

        order.splice(targetIndex, 0, movedId);
        this.columnOrder = order;
        this.saveColumnOrder();
        this.state.columns = this.getActiveColumns(this.props.list);
        this.preventReorder = true;
    },
});
