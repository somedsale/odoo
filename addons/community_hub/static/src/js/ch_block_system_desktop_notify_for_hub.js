/** @odoo-module **/

const TAG = "[CH-BLOCK-SYSTEM-DESKTOP]";
if (!window.__CH_BLOCK_SYSTEM_DESKTOP__) {
  window.__CH_BLOCK_SYSTEM_DESKTOP__ = true;

  const HUB_RE = /community\.hub/i; // match "community.hub.post,210"

  const toText = (x) => {
    if (x === null || x === undefined) return "";
    try {
      if (typeof x === "string") return x;
      if (typeof x === "object") {
        // NotificationOptions.body thường là string; nhưng cứ stringify nhẹ để bắt
        return JSON.stringify(x);
      }
      return String(x);
    } catch {
      return String(x || "");
    }
  };

  const shouldBlock = (title, options) => {
    const t = toText(title);
    const o = options || {};
    const b = toText(o.body);
    const data = toText(o.data);

    // ✅ chặn đúng loại “cũ” đang hiện (có community.hub.post,###)
    if (HUB_RE.test(t) || HUB_RE.test(b) || HUB_RE.test(data)) return true;

    // (optional) nếu bạn đặt subject prefix "[Community Hub]" thì chặn luôn
    if (/\[community hub\]/i.test(t) || /\[community hub\]/i.test(b)) return true;

    return false;
  };

  // ------------------------------
  // 1) Block window.Notification
  // ------------------------------
  const NativeNotification = window.Notification;
  if (NativeNotification) {
    function WrappedNotification(title, options) {
      if (shouldBlock(title, options)) {
        console.log(TAG, "BLOCK Notification()", { title, options });
        // object giả để code set onclick/close không crash
        return { close() {}, onclick: null };
      }
      return new NativeNotification(title, options);
    }
    WrappedNotification.prototype = NativeNotification.prototype;
    WrappedNotification.requestPermission = NativeNotification.requestPermission?.bind(NativeNotification);
    Object.defineProperty(WrappedNotification, "permission", { get: () => NativeNotification.permission });
    window.Notification = WrappedNotification;
  } else {
    console.warn(TAG, "window.Notification not available");
  }

  // --------------------------------------------
  // 2) Block ServiceWorkerRegistration.showNotification
  // (nhiều hệ thống bắn desktop theo đường này)
  // --------------------------------------------
  const SWR = window.ServiceWorkerRegistration?.prototype;
  if (SWR?.showNotification) {
    const nativeShow = SWR.showNotification;
    SWR.showNotification = function (title, options) {
      if (shouldBlock(title, options)) {
        console.log(TAG, "BLOCK showNotification()", { title, options });
        return Promise.resolve();
      }
      return nativeShow.call(this, title, options);
    };
  } else {
    // không có service worker cũng không sao
    console.log(TAG, "ServiceWorkerRegistration.showNotification not found (ok)");
  }

  console.log(TAG, "installed ✅");
}
