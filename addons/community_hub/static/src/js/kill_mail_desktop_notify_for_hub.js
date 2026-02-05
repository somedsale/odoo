/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { DesktopNotificationService } from "@mail/core/web/desktop_notification_service";

const TAG = "[CH-KILL-MAIL-DESKTOP]";
console.log(TAG, "loaded ✅", { DesktopNotificationService });

function isHubMessage(msg) {
  const model = (
    msg?.res_model ||
    msg?.resModel ||
    msg?.model ||
    msg?.thread?.model ||
    ""
  ).toString();
  // ✅ vì notification cũ của bạn đang hiện community.hub.post,193 nên model chắc chắn là "community.hub.post"
  return model.startsWith("community.hub");
}

function wrap(fnName, fn) {
  return function (...args) {
    const msg = args?.[0];
    if (isHubMessage(msg)) {
      console.log(TAG, "SKIP", fnName, {
        id: msg?.id,
        model: msg?.res_model || msg?.model,
        res_id: msg?.res_id,
        subject: msg?.subject,
      });
      return; // ✅ chặn desktop notify kiểu cũ
    }
    return fn.apply(this, args);
  };
}

const proto = DesktopNotificationService?.prototype;
if (!proto) {
  console.warn(TAG, "DesktopNotificationService prototype not found");
} else {
  const names = Object.getOwnPropertyNames(proto);
  const candidates = [];

  for (const name of names) {
    if (name === "constructor") continue;
    const fn = proto[name];
    if (typeof fn !== "function") continue;

    const src = Function.prototype.toString.call(fn);
    // ✅ bắt mọi hàm thực sự tạo desktop notification
    if (
      src.includes("new Notification") ||
      src.includes("Notification.permission") ||
      src.includes("requestPermission")
    ) {
      candidates.push(name);
    }
  }

  if (!candidates.length) {
    console.warn(TAG, "No method contains Notification(). Methods:", names);
  } else {
    const ext = {};
    for (const name of candidates) {
      ext[name] = wrap(name, proto[name]);
    }
    patch(proto, ext);
    console.log(TAG, "patched methods ✅", candidates);
  }
}
