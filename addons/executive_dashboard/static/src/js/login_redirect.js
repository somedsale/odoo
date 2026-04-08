/** @odoo-module **/

import { Component, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class ExecutiveDashboardLoginRedirect extends Component {
    static template = "executive_dashboard.EmptyTemplate";

    setup() {
        this.user = useService("user");
        this.action = useService("action");

        onMounted(async () => {
            try {
                const hasDirectorGroup = await this.user.hasGroup("custom_director_role.group_director");

                if (!hasDirectorGroup) {
                    return;
                }

                const hash = window.location.hash || "";

                // Nếu đang mở 1 action rồi thì thôi
                if (hash.includes("action=")) {
                    return;
                }

                // Chỉ redirect 1 lần trong 1 phiên
                const redirected = sessionStorage.getItem("executive_dashboard_redirect_done");
                if (redirected === "1") {
                    return;
                }

                sessionStorage.setItem("executive_dashboard_redirect_done", "1");

                await this.action.doAction("executive_dashboard.action_executive_dashboard");
            } catch (error) {
                console.error("Executive dashboard login redirect error:", error);
                sessionStorage.removeItem("executive_dashboard_redirect_done");
            }
        });
    }
}

registry.category("main_components").add("executive_dashboard_login_redirect", {
    Component: ExecutiveDashboardLoginRedirect,
});