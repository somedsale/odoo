/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { DesktopNotificationService } from "@mail/core/web/desktop_notification_service";

const TAG = "[CH-SKIP-MAIL-DESKTOP]";
console.log(TAG, "loaded");

function isHubMessage(message) {
  const model =
    message?.res_model ||
    message?.resModel ||
    message?.model ||
    message?.thread?.model ||
    "";
  const subject = (message?.subject || "").toString();

  // ✅ 3 cách nhận diện hub message (cái nào có thì dính)
  return (
    // 1) model community hub (cái này chắc chắn có – vì notification cũ đang hiện community.hub.post,193)
    (typeof model === "string" && model.startsWith("community.hub")) ||
    // 2) có open_url field của bạn
    !!message?.community_hub_open_url ||
    // 3) subject prefix (nếu bạn có dùng)
    subject.startsWith("[Community Hub]")
  );
}

function buildPatch(proto) {
  const wrap = (name) =>
    function (...args) {
      const message = args?.[0];
      if (isHubMessage(message)) {
        console.log(TAG, "SKIP", name, message?.id, message?.res_model || message?.model);
        return;
      }
      return this._super(...args);
    };

  const out = {};
  // Odoo 17 có thể dùng 1 trong các hàm này → patch cái nào tồn tại
  for (const name of ["_notifyMessage", "_showDesktopNotification", "_displayDesktopNotification"]) {
    if (typeof proto[name] === "function") out[name] = wrap(name);
  }
  return out;
}

const proto = DesktopNotificationService?.prototype;
if (proto) {
  const ext = buildPatch(proto);
  if (Object.keys(ext).length) patch(proto, ext);
  else console.warn(TAG, "No known method found to patch (please grep mail desktop notification service).");
}
