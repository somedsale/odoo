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
        this.state = useState({
            name: "",
            url: "",
            isOpen: false,
        });
    }

    onBeforeOpen() {
        this.state.url = window.location.pathname + window.location.search;
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
            // Fallback below
        }
        // Fallback: extract from URL path
        const parts = window.location.pathname.split("/").filter(Boolean);
        return parts.length > 1 ? parts.slice(1).join(" / ") : "";
    }

    onNameInput(ev) {
        this.state.name = ev.target.value;
    }

    async onSave() {
        const name = this.state.name.trim();
        if (!name) {
            return;
        }
        await this.orm.create("ggg.favorite", [{
            name,
            url: this.state.url,
        }]);
        this.state.isOpen = false;
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
