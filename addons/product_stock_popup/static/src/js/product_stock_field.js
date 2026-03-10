/** @odoo-module **/

import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { usePopover } from "@web/core/popover/popover_hook";
import { ProductStockPopover } from "./product_stock_popover";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { useEffect, onMounted, onWillUnmount } from "@odoo/owl";
import { ListRenderer } from "@web/views/list/list_renderer";

const ALLOWED_MODELS = [
    "purchase.order.line",
    "sale.order.line",
    "account.move.line"
];

const boundElements = new WeakSet();

patch(Many2OneField.prototype, {
    setup() {
        super.setup(...arguments);

        const isProductField = this.relation === "product.product" || this.relation === "product.template";
        const currentModel = this.props.record?.resModel;
        const isAllowedModel = currentModel && ALLOWED_MODELS.includes(currentModel);

        try {
            if (isProductField && isAllowedModel) {
                this.ormService = useService("orm");
                this.stockPopover = usePopover(ProductStockPopover, {
                    position: "right",
                });
                this._popoverTimeout = null;
                this._isMouseOver = false;
                this._boundElement = null;

                useEffect(
                    () => {
                        const timeoutId = setTimeout(() => {
                            try {
                                this._findAndBindElement();
                            } catch (e) { }
                        }, 50);

                        return () => {
                            clearTimeout(timeoutId);
                            try {
                                this._cleanupProductStockPopoverEvents();
                            } catch (e) { }
                        };
                    },
                    () => [this.value]
                );
            }
        } catch (e) { }
    },

    _findAndBindElement() {
        let el = null;

        if (!this.props?.readonly && this.autocompleteContainerRef?.el) {
            el = this.autocompleteContainerRef.el;
        }

        if (!el) {
            try {
                const node = this.__owl__;
                if (node && node.bdom) {
                    if (node.bdom.children) {
                        for (const child of node.bdom.children) {
                            if (child && child.el) {
                                el = child.el;
                                break;
                            }
                        }
                    }
                    if (!el && node.bdom.el) {
                        el = node.bdom.el;
                    }
                }
            } catch (e) { }
        }

        if (el && el !== this._boundElement && !boundElements.has(el)) {
            this._cleanupProductStockPopoverEvents();

            this._boundElement = el;
            boundElements.add(el);
            el.dataset.stockPopupBound = "true";
            const parentCell = el.closest("td.o_data_cell");
            if (parentCell) {
                parentCell.dataset.stockPopupBound = "true";
            }
            this._onMouseEnterBound = this._handleProductStockMouseEnter.bind(this);
            this._onMouseLeaveBound = this._handleProductStockMouseLeave.bind(this);
            el.addEventListener("mouseenter", this._onMouseEnterBound, true);
            el.addEventListener("mouseleave", this._onMouseLeaveBound, true);
        }
    },

    _cleanupProductStockPopoverEvents() {
        if (this._boundElement) {
            try {
                this._boundElement.removeEventListener("mouseenter", this._onMouseEnterBound, true);
                this._boundElement.removeEventListener("mouseleave", this._onMouseLeaveBound, true);
                boundElements.delete(this._boundElement);
            } catch (e) { }
            this._boundElement = null;
        }
        if (this._popoverTimeout) {
            clearTimeout(this._popoverTimeout);
        }
    },

    async _handleProductStockMouseEnter(ev) {
        try {
            if (this._popoverTimeout) {
                clearTimeout(this._popoverTimeout);
            }
            const targetElement = this._boundElement;

            this._popoverTimeout = setTimeout(async () => {
                try {
                    const value = this.value;
                    if (!value || !value[0]) {
                        return;
                    }

                    const stockInfo = await this.ormService.call(
                        "product.product",
                        "get_stock_info_for_popup",
                        [value[0]]
                    );

                    if (this._isMouseOver && targetElement) {
                        this.stockPopover.open(targetElement, {
                            stockInfo: stockInfo,
                            formatMoney: (val) => {
                                const n = Number(val || 0);
                                // format kiểu VN: 260,000
                                return n.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
                            },
                        });
                    }
                } catch (e) { }
            }, 300);

            this._isMouseOver = true;
        } catch (e) { }
    },

    _handleProductStockMouseLeave() {
        try {
            this._isMouseOver = false;
            if (this._popoverTimeout) {
                clearTimeout(this._popoverTimeout);
                this._popoverTimeout = null;
            }
            if (this.stockPopover) {
                this.stockPopover.close();
            }
        } catch (e) { }
    },
});


patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);

        this._stockPopupOrmService = useService("orm");
        this._stockPopupPopover = usePopover(ProductStockPopover, {
            position: "right",
        });
        this._stockPopupTimeout = null;
        this._stockPopupIsMouseOver = false;
        this._stockPopupCurrentTarget = null;

        this._stockPopupMouseEnter = this._handleStockPopupMouseEnter.bind(this);
        this._stockPopupMouseLeave = this._handleStockPopupMouseLeave.bind(this);

        onMounted(() => {
            this._attachStockPopupListeners();
        });

        onWillUnmount(() => {
            this._detachStockPopupListeners();
        });
    },

    _attachStockPopupListeners() {
        try {
            const el = this.__owl__?.bdom?.el;
            if (el) {
                el.addEventListener("mouseenter", this._stockPopupMouseEnter, true);
                el.addEventListener("mouseleave", this._stockPopupMouseLeave, true);
            }
        } catch (e) { }
    },

    _detachStockPopupListeners() {
        try {
            const el = this.__owl__?.bdom?.el;
            if (el) {
                el.removeEventListener("mouseenter", this._stockPopupMouseEnter, true);
                el.removeEventListener("mouseleave", this._stockPopupMouseLeave, true);
            }
            if (this._stockPopupTimeout) {
                clearTimeout(this._stockPopupTimeout);
            }
            if (this._stockPopupPopover) {
                this._stockPopupPopover.close();
            }
        } catch (e) { }
    },

    _handleStockPopupMouseEnter(ev) {
        try {
            const currentModel = this.props.list?.resModel;
            if (!currentModel || !ALLOWED_MODELS.includes(currentModel)) {
                return;
            }

            const target = ev.target;
            const cell = target.closest("td.o_data_cell");
            if (!cell) return;

            const fieldName = cell.dataset?.field || cell.getAttribute("name");
            if (!fieldName || fieldName !== "product_id") {
                return;
            }

            if (cell.dataset?.stockPopupBound === "true") {
                return;
            }

            const row = cell.closest("tr.o_data_row");
            if (!row) return;

            const resId = row.dataset?.id;
            if (!resId) return;

            if (this._stockPopupTimeout) {
                clearTimeout(this._stockPopupTimeout);
            }

            this._stockPopupIsMouseOver = true;
            this._stockPopupCurrentTarget = cell;

            const record = this.props.list?.records?.find(r => r.id === resId);
            if (!record) return;

            const productField = record.data[fieldName];
            if (!productField || !productField[0]) return;

            const productId = productField[0];

            this._stockPopupTimeout = setTimeout(async () => {
                try {
                    const stockInfo = await this._stockPopupOrmService.call(
                        "product.product",
                        "get_stock_info_for_popup",
                        [productId]
                    );

                    if (this._stockPopupIsMouseOver && this._stockPopupCurrentTarget === cell) {
                        this._stockPopupPopover.open(cell, {
                            stockInfo: stockInfo,
                            formatMoney: (val) => {
                                const n = Number(val || 0);
                                return n.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
                            },
                        });
                    }
                } catch (e) { }
            }, 300);
        } catch (e) { }
    },

    _handleStockPopupMouseLeave(ev) {
        try {
            const target = ev.target;
            const cell = target.closest("td.o_data_cell");
            if (!cell) return;

            const fieldName = cell.dataset?.field || cell.getAttribute("name");
            if (!fieldName || fieldName !== "product_id") {
                return;
            }

            this._stockPopupIsMouseOver = false;
            this._stockPopupCurrentTarget = null;

            if (this._stockPopupTimeout) {
                clearTimeout(this._stockPopupTimeout);
                this._stockPopupTimeout = null;
            }
            if (this._stockPopupPopover) {
                this._stockPopupPopover.close();
            }
        } catch (e) { }
    },
});
