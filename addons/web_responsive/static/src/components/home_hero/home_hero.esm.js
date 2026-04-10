/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { session } from "@web/session";
import { useBus, useService } from "@web/core/utils/hooks";
import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";

export class HomeHero extends Component {
    setup() {
        this.user = useService("user");
        this.router = useService("router");

        this.state = useState({
            open: false,
            launcherOpen: false,
            now: new Date(),
            greeting: "",
            userName: this.user.name || "User",
            theme: session.apps_menu?.theme || "milk",
        });

        this._timer = null;
        this._onHashChange = null;

        this._setGreeting();

        onMounted(() => {
            this._timer = setInterval(() => {
                this.state.now = new Date();
                this._setGreeting();
            }, 1000);

            this._onHashChange = () => {
                setTimeout(() => this._closeIfNavigated(), 0);
            };
            window.addEventListener("hashchange", this._onHashChange);

            this._closeIfNavigated();
        });

        onWillUnmount(() => {
            if (this._timer) {
                clearInterval(this._timer);
                this._timer = null;
            }
            if (this._onHashChange) {
                window.removeEventListener("hashchange", this._onHashChange);
                this._onHashChange = null;
            }
        });

        useBus(this.env.bus, "HOME_HERO:OPEN", () => {
            this._setGreeting();
            this.state.now = new Date();

            if (this._hasRealNavigation()) {
                this.closeHero();
                return;
            }

            this.state.open = true;
            this.env.bus.trigger("HOME_HERO:STATE_CHANGED", true);
        });

        useBus(this.env.bus, "HOME_HERO:CLOSE", () => {
            this.closeHero();
        });

        useBus(this.env.bus, "GGG_APP_LAUNCHER:STATE_CHANGED", ({ detail }) => {
            this.state.launcherOpen = !!detail;
        });

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => {
            this._closeIfNavigated();
        });

        useBus(this.env.bus, "ROUTE_CHANGE", () => {
            this._closeIfNavigated();
        });
    }

    _setGreeting() {
        const hour = this.state.now.getHours();
        if (hour < 12) {
            this.state.greeting = "Chào buổi sáng";
        } else if (hour < 18) {
            this.state.greeting = "Chào buổi chiều";
        } else {
            this.state.greeting = "Chào buổi tối";
        }
    }

    closeHero() {
        if (!this.state.open) {
            return;
        }
        this.state.open = false;
        this.env.bus.trigger("HOME_HERO:STATE_CHANGED", false);
    }

    _getHashValues() {
        const routerHash = this.router.current?.hash || {};
        const urlHash = {};
        const rawHash = window.location.hash ? window.location.hash.replace(/^#/, "") : "";
        const params = new URLSearchParams(rawHash);

        for (const [key, value] of params.entries()) {
            urlHash[key] = value;
        }

        return {
            ...urlHash,
            ...routerHash,
        };
    }

    _hasRealNavigation() {
        const hash = this._getHashValues();
        return Boolean(
            hash.menu_id ||
            hash.action ||
            hash.model ||
            hash.view_type ||
            hash.id ||
            hash.active_id
        );
    }

    _closeIfNavigated() {
        if (this._hasRealNavigation()) {
            this.closeHero();
        }
    }

    openApps() {
        this.env.bus.trigger("GGG_APP_LAUNCHER:OPEN");
    }
}

HomeHero.template = "web_responsive.HomeHero";

patch(NavBar, {
    components: {
        ...NavBar.components,
        HomeHero,
    },
});