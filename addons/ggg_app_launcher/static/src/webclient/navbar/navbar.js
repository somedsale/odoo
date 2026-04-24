/** @odoo-module **/

import { useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";
import { NavBar } from "@web/webclient/navbar/navbar";
import { AppLauncher } from "@ggg_app_launcher/webclient/app_launcher/app_launcher";

patch(NavBar, {
    components: {
        ...NavBar.components,
        AppLauncher,
    },
});

patch(NavBar.prototype, {
    setup() {
        super.setup();

        this.gggState = useState({
            launcherOpen: false,
        });

        useBus(this.env.bus, "GGG_APP_LAUNCHER:TOGGLE", () => {
            this.toggleGggLauncher();
        });

        useBus(this.env.bus, "GGG_APP_LAUNCHER:OPEN", () => {
            this.openGggLauncher();
        });

        useBus(this.env.bus, "GGG_APP_LAUNCHER:CLOSE", () => {
            this.closeGggLauncher();
        });
    },

    toggleGggLauncher() {
        if (this.gggState.launcherOpen) {
            this.closeGggLauncher();
        } else {
            this.openGggLauncher();
        }
    },

    openGggLauncher() {
        if (this.gggState.launcherOpen) {
            return;
        }
        this.gggState.launcherOpen = true;
        this.env.bus.trigger("GGG_APP_LAUNCHER:STATE_CHANGED", true);
    },

    closeGggLauncher() {
        if (!this.gggState.launcherOpen) {
            return;
        }
        this.gggState.launcherOpen = false;
        this.env.bus.trigger("GGG_APP_LAUNCHER:STATE_CHANGED", false);
    },
});