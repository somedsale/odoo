/** @odoo-module **/

import { onWillStart } from "@odoo/owl";
import { WebClient } from "@web/webclient/webclient";
import { patch } from "@web/core/utils/patch";
import { useBus, useService } from "@web/core/utils/hooks";

patch(WebClient.prototype, {
    setup() {
        super.setup();

        this.user = useService("user");
        this.orm = useService("orm");
        this.router = useService("router");

        useBus(this.env.bus, "HOME_HERO:STATE_CHANGED", ({ detail: state }) => {
            document.body.classList.toggle("o_home_hero_opened", !!state);
        });

        useBus(this.env.bus, "ROUTE_CHANGE", () => {
            document.body.classList.remove("o_home_hero_opened");
            this.env.bus.trigger("HOME_HERO:CLOSE");
        });

        onWillStart(async () => {
            const result = await this.orm.searchRead(
                "res.users",
                [["id", "=", this.user.userId]],
                ["is_redirect_home"]
            );

            this.env.services.user.updateContext({
                is_redirect_to_home: result[0]?.is_redirect_home || false,
            });
        });
    },

    _loadDefaultApp() {
        const ctx = this.env.services.user.context || {};
        const hash = this.router.current?.hash || {};
        const hasNavigation = !!(
            hash.menu_id ||
            hash.action ||
            hash.model ||
            hash.view_type ||
            hash.id
        );

        if (ctx.is_redirect_to_home && !hasNavigation) {
            this.env.bus.trigger("HOME_HERO:OPEN");
            return;
        }

        return super._loadDefaultApp();
    },
});