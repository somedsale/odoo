/** @odoo-module **/

import { registry } from "@web/core/registry";

const SOUND_URL = "/smd_mail_force_sound/static/src/audio/my_sound.mp3";
let audio = null;
let lastPlay = 0;

/** phát âm thanh mặc định */
function playDefaultSound() {
    const now = Date.now();
    if (now - lastPlay < 1200) return; // chống spam
    lastPlay = now;

    if (!audio) {
        audio = new window.Audio(SOUND_URL);
        audio.loop = false;
        audio.volume = 1.0;
        audio.preload = "auto";
    }
    audio.currentTime = 0;
    audio.play().catch(() => {
        console.warn("⚠️ Browser chặn autoplay, click 1 lần trong tab Odoo để bật âm thanh.");
    });
}

registry.category("services").add("smd_force_default_sound", {
    dependencies: ["bus_service", "user"],

    async start(env, { bus_service, user }) {
        if (!user?.userId) return;
        if (window.__SMD_FORCE_DEFAULT_SOUND__) return;
        window.__SMD_FORCE_DEFAULT_SOUND__ = true;

        console.log("🔊 Force default Discuss sound ON");

        bus_service.start();

        bus_service.addEventListener("notification", ({ detail: notifications }) => {
            if (!Array.isArray(notifications)) return;
            for (const notif of notifications) {
                try {
                    // === Các dạng thông báo có thể chứa tin nhắn mới ===
                    const type = notif?.type || notif?.[0] || "";
                    const model = notif?.[1]?.model || "";

                    if (
                        // Tin nhắn riêng (DM)
                        (type && String(type).includes("mail.message")) ||
                        (model && model === "mail.message") ||
                        // Tin nhắn trong kênh Discuss
                        (type && (type.includes("discuss.channel/new_message") ||
                            type.includes("mail.channel/new_message")))
                    ) {
                        console.log("💬 New message event:", notif);
                        playDefaultSound();
                        break;
                    }
                } catch (err) {
                    console.warn("❌ Parse notif error", err);
                }
            }
        });
    },
});
