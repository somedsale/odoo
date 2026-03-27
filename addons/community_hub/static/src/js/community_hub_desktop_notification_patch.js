/** @odoo-module **/

import { registry } from "@web/core/registry";

const communityHubDesktopNotifyService = {
    dependencies: ["bus_service", "user", "notification"],

    start(env, { bus_service, user, notification }) {
        const uid = Number(user?.userId || user?.user_id || env?.services?.user?.userId || 0);
        if (!uid) {
            console.warn("[COMMUNITY_HUB] userId not found; skip desktop notify service");
            return;
        }

        const channelName = `community_hub_notify:${uid}`;
        bus_service.addChannel(channelName);

        // dedupe: tránh bắn 2 lần do bus notify hoặc reload
        const seen = new Map();
        const shouldSkip = (key, ttl = 2500) => {
            const now = Date.now();
            const last = seen.get(key) || 0;
            if (now - last < ttl) return true;
            seen.set(key, now);
            return false;
        };

        const safeRequestPermission = async () => {
            try {
                if (!("Notification" in window)) return false;
                if (Notification.permission === "granted") return true;
                if (Notification.permission === "denied") return false;
                // default
                const p = await Notification.requestPermission();
                return p === "granted";
            } catch (e) {
                return false;
            }
        };

        const showNoti = async ({ title, body, url, dedupe_key }) => {
            // Nếu đang focus app thì thường không cần desktop notify
            // (tuỳ bạn: muốn luôn luôn bắn thì bỏ điều kiện này)
            if (!document.hidden) return;

            const ok = await safeRequestPermission();
            if (!ok) return;

            const key = dedupe_key || `${title || ""}|${body || ""}|${url || ""}`;
            if (shouldSkip(key)) return;

            try {
                const n = new Notification(title || "Community Hub", { body: body || "" });
                n.onclick = () => {
                    try { window.focus(); } catch (e) {}
                    if (url) window.location.assign(url);
                    try { n.close(); } catch (e) {}
                };
            } catch (e) {
                // fallback: thông báo trong app
                notification?.add?.(body || "Community Hub notification", { type: "info" });
            }
        };

        const normalizeNotifications = (evDetail) => {
            // ev.detail có thể là:
            // 1) [[channel, payload], ...]
            // 2) [{type, payload}, ...]
            // 3) {notifications: ...}
            let list = evDetail;
            if (!Array.isArray(list)) list = evDetail?.notifications;
            if (!Array.isArray(list)) return [];
            return list;
        };

        const handler = (ev) => {
            const notificationsList = normalizeNotifications(ev?.detail);

            for (const item of notificationsList) {
                let channel = null;
                let payload = null;

                if (Array.isArray(item)) {
                    // [[channel, payload]]
                    channel = item[0];
                    payload = item[1];
                } else if (item && typeof item === "object") {
                    // [{type, payload}] hoặc object payload thẳng
                    channel = item.type || item.channel || null;
                    payload = item.payload || item;
                }

                if (!payload) continue;

                // Filter đúng channel (khuyến nghị)
                // hoặc fallback theo payload.type nếu bạn gửi payload.type = "community_hub_notify"
                const isOurChannel = channel === channelName;
                const isOurPayloadType = payload?.type === "community_hub_notify";

                if (!isOurChannel && !isOurPayloadType) continue;

                // Chuẩn hoá payload
                const title = payload?.title || "Community Hub";
                const body = payload?.body || payload?.message || "";
                const url = payload?.url || payload?.open_url || null;
                const dedupe_key =
                    payload?.dedupe_key ||
                    `${payload?.type || "hub"}:${payload?.community_id || 0}:${payload?.channel_id || 0}:${payload?.post_id || 0}:${payload?.comment_id || 0}`;

                showNoti({ title, body, url, dedupe_key });
            }
        };

        bus_service.addEventListener("notification", handler);

        // Thường không cần gọi start() vì Odoo đã start bus rồi,
        // nhưng gọi cũng OK vì idempotent (tùy phiên bản).
        try { bus_service.start(); } catch (e) {}

        console.log("[COMMUNITY_HUB] desktop notify service loaded", { channel: channelName });
    },
};

registry.category("services").add("community_hub_desktop_notify_service", communityHubDesktopNotifyService);
