/** @odoo-module **/
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { useRef, useState, onMounted, onPatched, onWillUpdateProps } from "@odoo/owl";

export class One2ManySearch extends X2ManyField {
    setup() {
        super.setup();
        this.state = useState({ showSearchBar: false });
        this.searchRef = useRef("o2m_search_input");

        const recompute = () => this._recomputeVisibility();

        onMounted(recompute);
        onPatched(recompute);
        onWillUpdateProps(() => {
            // đợi props apply xong rồi mới tính
            setTimeout(recompute, 0);
        });
    }

    _getX2mRoot() {
        const el = this.searchRef?.el || this.el;
        return el?.closest?.(".o_field_x2many") || null;
    }

    _countRealRows(x2mRoot) {
        const table = x2mRoot?.querySelector(".o_list_table");
        const tbody = table?.querySelector("tbody");
        if (!tbody) return 0;

        const ids = new Set();
        for (const tr of tbody.querySelectorAll("tr.o_data_row")) {
            // row thật thường có data-id hoặc data-res-id
            const id =
                tr.getAttribute("data-id") ||
                tr.getAttribute("data-res-id") ||
                tr.dataset?.id ||
                tr.dataset?.resId;

            if (!id) continue;

            // loại mấy row “ảo” hay gặp (an toàn)
            if (tr.classList.contains("o_new_row")) continue;
            if (tr.classList.contains("o_list_record_empty")) continue;

            ids.add(String(id));
        }
        return ids.size;
    }

    _recomputeVisibility() {
        const x2mRoot = this._getX2mRoot();
        if (!x2mRoot) return;

        const count = this._countRealRows(x2mRoot);
        const shouldShow = count > 1;

        if (this.state.showSearchBar !== shouldShow) {
            this.state.showSearchBar = shouldShow;

            // nếu vừa ẩn thì clear + reset filter
            if (!shouldShow) {
                const input = this.searchRef?.el;
                if (input) input.value = "";

                const table = x2mRoot.querySelector(".o_list_table");
                if (table) {
                    for (const tr of table.querySelectorAll("tbody tr.o_data_row")) {
                        tr.classList.remove("o_hidden_by_o2m_search");
                    }
                }
            }
        }
    }

    onInputKeyUp(ev) {
        const value = (ev.target.value || "").toLowerCase();
        const x2mRoot = this._getX2mRoot();
        if (!x2mRoot) return;

        const table = x2mRoot.querySelector(".o_list_table");
        if (!table) return;

        for (const tr of table.querySelectorAll("tbody tr.o_data_row")) {
            const txt = (tr.textContent || "").toLowerCase();
            tr.classList.toggle("o_hidden_by_o2m_search", value && !txt.includes(value));
        }
    }
}

One2ManySearch.template = "One2ManySearchTemplate";

export const one2ManySearch = {
    ...x2ManyField,
    component: One2ManySearch,
};

const fieldsReg = registry.category("fields");
fieldsReg.add("one2many_search", one2ManySearch);
fieldsReg.add("one2many", one2ManySearch, { force: true });

console.log("[one2many_search] loaded ✅");
