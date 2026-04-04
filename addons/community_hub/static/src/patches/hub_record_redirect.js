/** @odoo-module **/

import { registry } from "@web/core/registry";

console.log("[community_hub] hub_record_redirect patch loaded ✅");

const HUB_MODELS = new Set(["community.hub.post", "community.hub.channel", "community.hub"]);

function isHubActWindow(action) {
  return (
    action &&
    typeof action === "object" &&
    action.type === "ir.actions.act_window" &&
    action.res_model &&
    action.res_id &&
    HUB_MODELS.has(action.res_model)
  );
}

(function patchActionService() {
  const services = registry.category("services");
  const def = services.get("action");
  if (!def || typeof def.start !== "function") {
    console.warn("[community_hub] action service definition not found");
    return;
  }

  const originalStart = def.start;

  // monkey-patch start() để wrap service instance
  def.start = function (env, deps) {
    const service = originalStart.call(this, env, deps);
    if (!service || typeof service.doAction !== "function") return service;

    const originalDoAction = service.doAction.bind(service);

    service.doAction = async function (actionRequest, options = {}) {
      try {
        // chỉ chặn khi click mở form record của hub
        if (isHubActWindow(actionRequest)) {
          const rpc = env.services.rpc;

          const info = await rpc("/community_hub/resolve_deeplink", {
            model: actionRequest.res_model,
            res_id: actionRequest.res_id,
          });

          const ids = await rpc("/community_hub/action_menu_ids", {});

          const params = new URLSearchParams();
          if (ids?.action_id) params.set("action", String(ids.action_id));
          if (ids?.menu_id) params.set("menu_id", String(ids.menu_id));
          if (info?.community_id) params.set("community_id", String(info.community_id));
          if (info?.channel_id) params.set("channel_id", String(info.channel_id));
          if (info?.post_id) params.set("post_id", String(info.post_id));
          params.set("tab", "posts");

          // ✅ chuyển sang dashboard
          window.location.hash = params.toString();
          return; // chặn không mở form
        }
      } catch (e) {
        console.warn("[community_hub] redirect failed, fallback to normal action", e);
      }

      return await originalDoAction(actionRequest, options);
    };

    return service;
  };
})();
