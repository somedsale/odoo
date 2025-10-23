/** @odoo-module **/

import { registry } from "@web/core/registry";

const SOUND_URL = "/smd_mail_force_sound/static/src/audio/my_sound.mp3";
let audio = null, lastPlay = 0;

function playDefaultSound() {
    const now = Date.now();
    if (now - lastPlay < 1200) return;
    lastPlay = now;
    (audio ??= Object.assign(new Audio(SOUND_URL), { loop: false, volume: 1.0, preload: "auto" }));
    audio.currentTime = 0;
    audio.play().catch(() => console.warn("⚠️ Click 1 lần trong tab Odoo để bật âm thanh."));
}

registry.category("services").add("smd_force_default_sound", {
    dependencies: ["bus_service", "user"],

    start(env, { bus_service, user }) {
        if (!user?.userId || window.__SMD_FORCE_DEFAULT_SOUND__) return;
        window.__SMD_FORCE_DEFAULT_SOUND__ = true;
        const selfPartnerId = user.partner_id || user.partnerId;
        console.log("🔊 Force default Discuss sound ON (partner:", selfPartnerId, ")");

        bus_service.start();

        bus_service.addEventListener("notification", ({ detail }) => {
            if (!Array.isArray(detail)) return;

            for (const notif of detail) {
                const type = notif?.type || notif?.[0] || "";
                if (!type?.includes("mail") && !type?.includes("discuss.channel")) continue;

                // 👉 Bắt message gốc
                const msg =
                    notif?.payload?.message?.message?.message ||
                    notif?.payload?.message?.message ||
                    notif?.payload?.data?.[0] ||
                    notif?.payload?.message?.data?.[0];
                console.log("💬 DEBUG:", { type, msg });

                const author = msg?.author_id?.[0];
                const partners = (msg?.partner_ids || []).map(p => Array.isArray(p) ? p[0] : p);

                console.log("💬 DEBUG:", { author, partners, selfPartnerId, msg });

                // Không phát nếu là chính mình gửi
                if (author && author === selfPartnerId) continue;

                // Chỉ phát nếu mình nằm trong danh sách nhận
                if (partners.includes(selfPartnerId)) playDefaultSound();
            }
        });
    },
});
