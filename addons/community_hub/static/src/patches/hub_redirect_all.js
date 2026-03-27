/** @odoo-module **/

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

const TAG = "[community_hub][hub_redirect_all]";
const HUB_MODELS = new Set(["community.hub.post", "community.hub.channel", "community.hub"]);

function safePatch(obj, name, ext) {
    try {
        // Odoo 17
        patch(obj, ext);
    } catch (e) {
        // Odoo 16 fallback
        patch(obj, name, ext);
    }
}

function parseHashParams(env) {
    try {
        const raw =
            (env?.services?.router?.current?.hash || window.location.hash || "")
                .replace(/^#/, "");
        const params = new URLSearchParams(raw);
        const model = params.get("model") || "";
        const id = Number(params.get("id") || 0);
        return { model, id };
    } catch {
        return { model: "", id: 0 };
    }
}

async function computeHubParams(env, model, id) {
    const orm = env?.services?.orm;
    if (!orm || !model || !id) return null;

    if (model === "community.hub.post") {
        const [r] = await orm.read(model, [id], ["community_id", "channel_id"]);
        const community_id = r?.community_id?.[0] || 0;
        const channel_id = r?.channel_id?.[0] || 0;
        if (!community_id) return null;
        return { community_id, channel_id, post_id: id, tab: "posts" };
    }

    if (model === "community.hub.channel") {
        const [r] = await orm.read(model, [id], ["community_id"]);
        const community_id = r?.community_id?.[0] || 0;
        if (!community_id) return null;
        return { community_id, channel_id: id, post_id: 0, tab: "posts" };
    }

    if (model === "community.hub") {
        return { community_id: id, channel_id: 0, post_id: 0, tab: "posts" };
    }

    return null;
}

/**
 * 1) Intercept “in-app” navigation: doAction(act_window mở form) -> đổi sang client action hub
 *    (click link trong chatter, inbox, many2one, openRecord...)
 */
(function installActionDoActionRedirect() {
    const services = registry.category("services");
    const def = services.get("action");
    if (!def) {
        console.warn(TAG, "service 'action' not found");
        return;
    }
    if (def.__hub_redirect_patched__) return;
    def.__hub_redirect_patched__ = true;

    const originalStart = def.start;

    def.start = async function (env, deps) {
        const service = await originalStart.call(this, env, deps);
        if (service.__hub_redirect_wrapped__) return service;
        service.__hub_redirect_wrapped__ = true;

        const originalDoAction = service.doAction.bind(service);

        service.doAction = async (actionRequest, options = {}) => {
            try {
                // tránh loop
                if (options.__hub_redirect_done) {
                    return originalDoAction(actionRequest, options);
                }

                // act_window mở record form thường là object có res_model/res_id
                const ar = actionRequest;
                const model = ar?.res_model;
                const id = Number(ar?.res_id || 0);

                if (ar?.type === "ir.actions.act_window" && HUB_MODELS.has(model) && id) {
                    const params = await computeHubParams(env, model, id);
                    if (params?.community_id) {
                        console.log(TAG, "doAction redirect", { model, id, params });
                        return originalDoAction(
                            {
                                type: "ir.actions.client",
                                tag: "community_hub.client_action",
                                name: "Community Hub",
                                params,
                            },
                            { ...options, __hub_redirect_done: true, clearBreadcrumbs: true, replace: true }
                        );
                    }
                }
            } catch (e) {
                console.warn(TAG, "doAction redirect failed -> fallback", e);
            }
            return originalDoAction(actionRequest, options);
        };

        return service;
    };
})();

/**
 * 2) Intercept “direct URL open” (desktop notification mở /web#model=...&id=...)
 *    -> đổi sang client action hub ngay khi WebClient load router state
 */
safePatch(WebClient.prototype, "community_hub.webclient_router_redirect", {
    async loadRouterState() {
        try {
            const { model, id } = parseHashParams(this.env);

            if (HUB_MODELS.has(model) && id) {
                const actionService = this.env.services.action;
                const params = await computeHubParams(this.env, model, id);

                if (params?.community_id && actionService?.doAction) {
                    console.log(TAG, "router redirect", { model, id, params });
                    await actionService.doAction(
                        {
                            type: "ir.actions.client",
                            tag: "community_hub.client_action",
                            name: "Community Hub",
                            params,
                        },
                        { __hub_redirect_done: true, clearBreadcrumbs: true, replace: true }
                    );
                    return; // ✅ chặn mở form view
                }
            }
        } catch (e) {
            console.warn(TAG, "router redirect failed -> fallback", e);
        }
        return await super.loadRouterState(...arguments);
    },
});

console.log(TAG, "loaded ✅");
