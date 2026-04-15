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
        this.orm = useService("orm");

        this.state = useState({
            open: false,
            launcherOpen: false,
            now: new Date(),
            greeting: "",
            userName: this.user.name || "User",
            theme: session.apps_menu?.theme || "milk",
            upcomingEvents: [],
            loadingEvents: false,
            onlineUserCount: 0,
        });

        this._timer = null;
        this._onHashChange = null;
        this._onlineReloadTimer = null;

        this._setGreeting();

        onMounted(() => {
            this._timer = setInterval(() => {
                this.state.now = new Date();
                this._setGreeting();
            }, 1000);

            // refresh số user online mỗi 60s


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
            if (this._onlineReloadTimer) {
                clearInterval(this._onlineReloadTimer);
                this._onlineReloadTimer = null;
            }
            if (this._onHashChange) {
                window.removeEventListener("hashchange", this._onHashChange);
                this._onHashChange = null;
            }
        });

        useBus(this.env.bus, "HOME_HERO:OPEN", async () => {
            this._setGreeting();
            this.state.now = new Date();

            if (this._hasRealNavigation()) {
                this.closeHero();
                return;
            }

            this.state.open = true;
            this.env.bus.trigger("HOME_HERO:STATE_CHANGED", true);

            await Promise.all([
                this.loadUpcomingEvents(),
            ]);
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

    async loadUpcomingEvents() {
        this.state.loadingEvents = true;
        this.state.upcomingEvents = [];

        try {
            const nowStr = this._toServerDatetime(new Date());
            const partnerId = session.partner_id;

            let domain = [
                ["stop", ">=", nowStr],
            ];

            if (partnerId) {
                domain = [
                    "&",
                    ["stop", ">=", nowStr],
                    ["partner_ids", "in", [partnerId]],
                ];
            }

            const fields = [
                "id",
                "name",
                "start",
                "stop",
                "location",
                "allday",
                "partner_ids",
            ];

            const events = await this.orm.call(
                "calendar.event",
                "search_read",
                [],
                {
                    domain,
                    fields,
                    limit: 5,
                    order: "start asc",
                    context: session.user_context || {},
                }
            );

            this.state.upcomingEvents = Array.isArray(events) ? events : [];
        } catch (error) {
            console.error("HomeHero: loadUpcomingEvents error", error);
            this.state.upcomingEvents = [];
        } finally {
            this.state.loadingEvents = false;
        }
    }



    _toServerDatetime(date) {
        const pad = (n) => String(n).padStart(2, "0");
        return (
            date.getFullYear() +
            "-" +
            pad(date.getMonth() + 1) +
            "-" +
            pad(date.getDate()) +
            " " +
            pad(date.getHours()) +
            ":" +
            pad(date.getMinutes()) +
            ":" +
            pad(date.getSeconds())
        );
    }

    _parseDate(value) {
        if (!value) {
            return null;
        }
        try {
            if (typeof value === "string" && value.indexOf("T") === -1) {
                return new Date(value.replace(" ", "T"));
            }
            return new Date(value);
        } catch (e) {
            return null;
        }
    }

    formatEventMonth(dateValue) {
        const date = this._parseDate(dateValue);
        if (!date || isNaN(date.getTime())) {
            return "";
        }
        return date.toLocaleString("en-US", { month: "short" }).toUpperCase();
    }

    formatEventDay(dateValue) {
        const date = this._parseDate(dateValue);
        if (!date || isNaN(date.getTime())) {
            return "";
        }
        return String(date.getDate());
    }

    formatEventTime(dateValue) {
        const date = this._parseDate(dateValue);
        if (!date || isNaN(date.getTime())) {
            return "";
        }
        return date.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });
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