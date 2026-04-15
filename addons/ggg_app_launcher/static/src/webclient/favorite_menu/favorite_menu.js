/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class FavoriteMenu extends Component {
    static components = { Dropdown };
    static props = [];
    static template = "ggg_app_launcher.FavoriteMenu";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            name: "",
            url: "",
            isOpen: false,
        });
    }

    onBeforeOpen() {
        this.state.url = window.location.pathname + window.location.hash;
        this.state.name = this._getPageName();
    }

    _getPageName() {
        try {
            const controller = this.action.currentController;
            if (controller && controller.config && controller.config.getDisplayName) {
                const name = controller.config.getDisplayName();
                if (name) {
                    return name;
                }
            }
        } catch {
            // fallback below
        }

        const parts = window.location.pathname.split("/").filter(Boolean);
        return parts.length > 1 ? parts.slice(1).join(" / ") : "";
    }

    onNameInput(ev) {
        this.state.name = ev.target.value;
    }

    async onSave() {
        const name = this.state.name.trim();
        if (!name) {
            this.notification.add("Vui lòng nhập tên yêu thích.", {
                type: "warning",
            });
            return;
        }

        try {
            await this.orm.create("ggg.favorite", [{
                name,
                url: this.state.url,
            }]);

            this.notification.add("Đã lưu vào yêu thích thành công.", {
                type: "success",
            });

            this.state.isOpen = false;
        } catch (error) {
            console.error("Favorite save error", error);
            this.notification.add("Lưu yêu thích thất bại.", {
                type: "danger",
            });
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            this.onSave();
        }
    }
}

registry.category("systray").add(
    "ggg_app_launcher.favorite_menu",
    { Component: FavoriteMenu },
    { sequence: 25 },
);