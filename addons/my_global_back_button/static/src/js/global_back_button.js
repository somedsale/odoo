/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched } from "@odoo/owl";
import { ControlPanel } from "@web/search/control_panel/control_panel";

function doBack(env) {
    if (window.history.length > 1) {
        window.history.back();
        return;
    }
    env.services.action?.restore?.();
}

function isDialog(el) {
    return !!el?.closest(".modal, .o_dialog");
}

function getCurrentViewType(cp) {
    // ưu tiên lấy từ searchModel/config nếu có
    return (
        cp.props?.info?.viewType ||
        cp.props?.viewType ||
        cp.env?.searchModel?.config?.viewType ||
        cp.env?.config?.viewType ||
        null
    );
}

function injectBackButton(cp) {
    const root = cp.el;
    if (!root) return;
    if (isDialog(root)) return;

    const viewType = getCurrentViewType(cp);
    if (!["form", "list"].includes(viewType)) {
        return;
    }

    const breadcrumb = root.querySelector(".breadcrumb, ol.breadcrumb");
    if (!breadcrumb || !breadcrumb.parentElement) {
        return;
    }

    if (root.querySelector(".o_global_back_btn")) {
        return;
    }

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-outline-secondary o_global_back_btn me-2";
    btn.innerHTML = '<i class="fa fa-arrow-left me-1"></i>Quay lại';
    btn.addEventListener("click", () => doBack(cp.env));

    breadcrumb.parentElement.insertBefore(btn, breadcrumb);
}

patch(ControlPanel.prototype, {
    setup() {
        super.setup(...arguments);

        onMounted(() => {
            injectBackButton(this);
        });

        onPatched(() => {
            injectBackButton(this);
        });
    },
});