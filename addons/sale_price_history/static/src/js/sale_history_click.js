/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class SaleHistoryListRenderer extends ListRenderer {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        onMounted(() => {
            const tbody = this.el.querySelector("tbody");
            if (!tbody) return;
            tbody.addEventListener("click", async (ev) => {
                const tr = ev.target.closest("tr");
                if (!tr) return;
                const resId = tr.dataset?.resId;
                if (!resId) return;

                const ctx = this.env.searchParams?.context || {};
                try {
                    const ok = await this.orm.call(
                        "sale.order.line",
                        "action_apply_history_price",
                        [[parseInt(resId, 10)]],
                        { context: ctx }
                    );
                    if (ok) {
                        // Thông báo đã bắn từ server, chỉ cần đóng popup là đủ
                        this.action.doAction({ type: "ir.actions.act_window_close" });
                    }
                } catch (e) {
                    console.error(e);
                    this.notification.add("Không thể áp dụng giá.", {
                        title: "Lỗi", type: "danger",
                    });
                }
            });
        });
    }
}

const SaleHistoryListView = {
    ...ListView,
    Renderer: SaleHistoryListRenderer,
};
registry.category("views").add("sale_history_list", SaleHistoryListView);
