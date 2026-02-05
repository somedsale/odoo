/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActionService } from "@web/core/action_service";

const HUB_MODELS = new Set(["community.hub.post", "community.hub.channel", "community.hub"]);

function safePatch(obj, name, extension) {
  try {
    return patch(obj, extension); // Odoo 17
  } catch (e) {
    return patch(obj, name, extension); // fallback Odoo 16
  }
}

safePatch(ActionService.prototype, "community_hub.action_redirect", {
  async doAction(action, options = {}) {
    // chỉ chặn khi action là object act_window mở record
    const a = action;
    if (
      a &&
      typeof a === "object" &&
      a.type === "ir.actions.act_window" &&
      HUB_MODELS.has(a.res_model) &&
      a.res_id
    ) {
      try {
        const rpc = this.env?.services?.rpc;
        const res = await rpc("/community_hub/hub_url_from_record", {
          res_model: a.res_model,
          res_id: a.res_id,
        });

        if (res?.ok && res?.url) {
          return await this._super(
            { type: "ir.actions.act_url", url: res.url, target: "self" },
            options
          );
        }
      } catch (e) {
        // lỗi thì fallback mở form như bình thường
      }
    }
    return await this._super(action, options);
  },
});
