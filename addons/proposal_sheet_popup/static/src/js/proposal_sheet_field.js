/** @odoo-module **/

import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { usePopover } from "@web/core/popover/popover_hook";
import { ProposalSheetPopover } from "./proposal_sheet_popover";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { useEffect, onMounted, onWillUnmount } from "@odoo/owl";
import { ListRenderer } from "@web/views/list/list_renderer";

// ✅ per your request
const ALLOWED_MODELS = ["account.payment.request"];
const ALLOWED_FIELDS = ["proposal_sheet_id", "proposal_display"];

const boundElements = new WeakSet();

function safeGetFieldNameFromCell(cell) {
    return cell?.dataset?.field || cell?.getAttribute("name") || "";
}

patch(Many2OneField.prototype, {
    setup() {
        super.setup(...arguments);

        const currentModel = this.props.record?.resModel;
        const fieldName = this.props?.name;

        const isAllowed =
            currentModel &&
            ALLOWED_MODELS.includes(currentModel) &&
            fieldName &&
            ALLOWED_FIELDS.includes(fieldName);

        const isProposal = this.relation === "proposal.sheet";
        if (!isAllowed || !isProposal) return;

        this.ormService = useService("orm");
        this.proposalPopover = usePopover(ProposalSheetPopover, { position: "right" });

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
                        this._cleanupProposalPopoverEvents();
                    } catch (e) { }
                };
            },
            () => [this.value]
        );
    },

    _findAndBindElement() {
        let el = null;

        // editable
        if (!this.props?.readonly && this.autocompleteContainerRef?.el) {
            el = this.autocompleteContainerRef.el;
        }

        // readonly fallback
        if (!el) {
            try {
                const node = this.__owl__;
                if (node?.bdom?.children) {
                    for (const child of node.bdom.children) {
                        if (child?.el) {
                            el = child.el;
                            break;
                        }
                    }
                }
                if (!el && node?.bdom?.el) el = node.bdom.el;
            } catch (e) { }
        }

        if (el && el !== this._boundElement && !boundElements.has(el)) {
            this._cleanupProposalPopoverEvents();

            this._boundElement = el;
            boundElements.add(el);

            el.dataset.proposalPopupBound = "true";
            const parentCell = el.closest("td.o_data_cell");
            if (parentCell) parentCell.dataset.proposalPopupBound = "true";

            this._onMouseEnterBound = this._handleProposalMouseEnter.bind(this);
            this._onMouseLeaveBound = this._handleProposalMouseLeave.bind(this);

            el.addEventListener("mouseenter", this._onMouseEnterBound, true);
            el.addEventListener("mouseleave", this._onMouseLeaveBound, true);
        }
    },

    _cleanupProposalPopoverEvents() {
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
            this._popoverTimeout = null;
        }
        try {
            this.proposalPopover?.close();
        } catch (e) { }
    },

    async _handleProposalMouseEnter() {
        try {
            if (this._popoverTimeout) clearTimeout(this._popoverTimeout);
            const targetElement = this._boundElement;
            this._isMouseOver = true;

            this._popoverTimeout = setTimeout(async () => {
                try {
                    const value = this.value;
                    if (!value || !value[0]) return;

                    const proposalInfo = await this.ormService.call(
                        "proposal.sheet",
                        "get_proposal_info_for_popup",
                        [value[0]]
                    );

                    if (this._isMouseOver && targetElement) {
                        this.proposalPopover.open(targetElement, { proposalInfo });
                    }
                } catch (e) { }
            }, 250);
        } catch (e) { }
    },

    _handleProposalMouseLeave() {
        try {
            this._isMouseOver = false;
            if (this._popoverTimeout) {
                clearTimeout(this._popoverTimeout);
                this._popoverTimeout = null;
            }
            this.proposalPopover?.close();
        } catch (e) { }
    },
});

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);

        // ✅ only activate on allowed model lists
        const currentModel = this.props.list?.resModel;
        this._proposalPopupEnabled = !!(currentModel && ALLOWED_MODELS.includes(currentModel));
        if (!this._proposalPopupEnabled) return;

        this._proposalOrm = useService("orm");
        this._proposalPopover = usePopover(ProposalSheetPopover, { position: "right" });

        this._proposalTimeout = null;
        this._proposalIsMouseOver = false;
        this._proposalCurrentTarget = null;

        this._proposalMouseEnter = this._handleProposalListMouseEnter.bind(this);
        this._proposalMouseLeave = this._handleProposalListMouseLeave.bind(this);

        onMounted(() => this._attachProposalListeners());
        onWillUnmount(() => this._detachProposalListeners());
    },

    _attachProposalListeners() {
        if (!this._proposalPopupEnabled) return;
        try {
            const el = this.__owl__?.bdom?.el;
            if (el) {
                el.addEventListener("mouseenter", this._proposalMouseEnter, true);
                el.addEventListener("mouseleave", this._proposalMouseLeave, true);
            }
        } catch (e) { }
    },

    _detachProposalListeners() {
        if (!this._proposalPopupEnabled) return;
        try {
            const el = this.__owl__?.bdom?.el;
            if (el) {
                el.removeEventListener("mouseenter", this._proposalMouseEnter, true);
                el.removeEventListener("mouseleave", this._proposalMouseLeave, true);
            }
            if (this._proposalTimeout) clearTimeout(this._proposalTimeout);
            this._proposalPopover?.close();
        } catch (e) { }
    },

    _handleProposalListMouseEnter(ev) {
        if (!this._proposalPopupEnabled) return;

        try {
            const cell = ev.target?.closest?.("td.o_data_cell");
            if (!cell) return;

            const fieldName = safeGetFieldNameFromCell(cell);
            if (!fieldName || !ALLOWED_FIELDS.includes(fieldName)) return;

            if (cell.dataset?.proposalPopupBound === "true") return;

            const row = cell.closest("tr.o_data_row");
            if (!row) return;

            const resId = row.dataset?.id;
            if (!resId) return;

            const records = this.props.list?.records || [];
            const record = records.find((r) => String(r.id) === String(resId));
            if (!record) return;

            const val = record.data[fieldName];
            if (!val || !val[0]) return;

            const proposalId = val[0];

            if (this._proposalTimeout) clearTimeout(this._proposalTimeout);

            this._proposalIsMouseOver = true;
            this._proposalCurrentTarget = cell;

            this._proposalTimeout = setTimeout(async () => {
                try {
                    const proposalInfo = await this._proposalOrm.call(
                        "proposal.sheet",
                        "get_proposal_info_for_popup",
                        [proposalId]
                    );
                    if (this._proposalIsMouseOver && this._proposalCurrentTarget === cell) {
                        this._proposalPopover.open(cell, { proposalInfo });
                    }
                } catch (e) { }
            }, 250);
        } catch (e) { }
    },

    _handleProposalListMouseLeave(ev) {
        if (!this._proposalPopupEnabled) return;

        try {
            const cell = ev.target?.closest?.("td.o_data_cell");
            if (!cell) return;

            const fieldName = safeGetFieldNameFromCell(cell);
            if (!fieldName || !ALLOWED_FIELDS.includes(fieldName)) return;

            this._proposalIsMouseOver = false;
            this._proposalCurrentTarget = null;

            if (this._proposalTimeout) {
                clearTimeout(this._proposalTimeout);
                this._proposalTimeout = null;
            }
            this._proposalPopover?.close();
        } catch (e) { }
    },
});
