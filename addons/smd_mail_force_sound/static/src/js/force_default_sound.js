/** @odoo-module **/

import { registry } from "@web/core/registry";

const SOUND_URL = "/smd_mail_force_sound/static/src/audio/my_sound.mp3";
let audio = null, lastPlay = 0;

function playDefaultSound() {
    const now = Date.now();
    if (now - lastPlay < 1200) return; // chống spam
    lastPlay = now;
    (audio ??= Object.assign(new Audio(SOUND_URL), { loop: false, volume: 1.0, preload: "auto" }));
    audio.currentTime = 0;
    audio.play().catch(() => console.warn("⚠️ Click 1 lần trong tab Odoo để bật âm thanh."));
}

/* -------------------- helpers chung -------------------- */
const tupleToId = (v) => Array.isArray(v) ? v[0] : v;

function isLikelyMessage(o) {
    if (!o || typeof o !== "object") return false;
    if (o.model === "mail.message") return true;
    return ("author_id" in o) || ("partner_ids" in o) || ("message_type" in o) || ("body" in o)
        || ("author" in o) || ("recipients" in o);
}

function deepFindMessage(root) {
    const q = [root];
    const seen = new WeakSet();
    let steps = 0, MAX = 800;
    while (q.length && steps < MAX) {
        const cur = q.shift(); steps++;
        if (isLikelyMessage(cur)) return cur;
        if (cur && typeof cur === "object" && !seen.has(cur)) {
            seen.add(cur);
            if (Array.isArray(cur)) q.push(...cur);
            else for (const k of Object.keys(cur)) q.push(cur[k]);
        }
    }
    return null;
}

function extractMsg(notif) {
    const p = notif?.payload;
    const cands = [
        p?.message?.message?.message,
        p?.message?.message,
        p?.message,
        p?.messages?.[0],
        p?.new_message,
        p?.data?.message,
        p?.data?.[0],
        p?.message?.data?.message,
        p?.message?.data?.[0],
        Array.isArray(notif) ? notif[1]?.message : null,
        Array.isArray(notif) ? notif[1]?.data?.[0] : null,
    ].filter(Boolean);
    for (const c of cands) if (isLikelyMessage(c)) return c;
    return deepFindMessage(notif);
}

function normalizeMessage(msg) {
    const authorId =
        tupleToId(msg.author_id) ||
        msg.author?.id ||
        msg.author?.partner?.id ||
        null;

    let partnerIds = [];
    if (Array.isArray(msg.partner_ids)) {
        partnerIds = msg.partner_ids.map(tupleToId);
    } else if (Array.isArray(msg.recipients)) {
        partnerIds = msg.recipients.map(r => r?.id).filter(Boolean);
    } else if (Array.isArray(msg.needaction_partner_ids)) {
        partnerIds = msg.needaction_partner_ids.map(tupleToId);
    } else if (Array.isArray(msg.notifications)) {
        partnerIds = msg.notifications
            .map(n => n?.partner?.id || tupleToId(n?.partner_id))
            .filter(Boolean);
    }

    const isDiscussChannel = msg.model === "discuss.channel";
    return { authorId, partnerIds, isDiscussChannel };
}

/* ---------- Lọc loại sự kiện: bỏ typing/seen/system ---------- */
function isTypingEvent(type, payload) {
    const t = String(type || "");
    if (t.includes("typing")) return true; // ví dụ: discuss.channel/typing_status
    const p = payload || {};
    // một số biến thể payload typing
    return !!(p?.typing || p?.is_typing || p?.info?.type === "typing");
}

function isSeenOrPresenceEvent(type, payload) {
    const t = String(type || "");
    if (t.includes("seen") || t.includes("presence")) return true;
    const p = payload || {};
    return !!(p?.seen || p?.presence);
}

function isNewMessageEvent(type, msg) {
    const t = String(type || "");
    // các pattern phổ biến cho message
    if (t.includes("new_message")) return true;                       // discuss.channel/new_message
    if (t.includes("mail.message") && t.includes("create")) return true; // mail.message/create
    // fallback theo nội dung message
    if (!msg) return false;
    // chỉ nhận comment (loại chat), bỏ note/system
    if (msg.message_type === "comment") return true;
    // 1 số hệ thống không set message_type nhưng có body/author ⇒ coi là message
    if (msg.body && (msg.author || msg.author_id)) return true;
    return false;
}

/* -------------------- service -------------------- */
registry.category("services").add("smd_force_default_sound", {
    dependencies: ["bus_service", "user"],

    start(env, { bus_service, user }) {
        if (!user?.userId || window.__SMD_FORCE_DEFAULT_SOUND__) return;
        window.__SMD_FORCE_DEFAULT_SOUND__ = true;
        const selfPartnerId = user.partner_id || user.partnerId;

        bus_service.start();

        bus_service.addEventListener("notification", ({ detail }) => {
            if (!Array.isArray(detail)) return;

            for (const notif of detail) {
                const type = notif?.type || notif?.[0] || "";
                const payload = notif?.payload || (Array.isArray(notif) ? notif[1] : null);

                // 1) Chỉ quan tâm mail/discuss
                const typeStr = String(type || "");
                if (!typeStr.includes("mail") && !typeStr.includes("discuss")) continue;

                // 2) BỎ qua typing/seen/presence
                if (isTypingEvent(type, payload) || isSeenOrPresenceEvent(type, payload)) {
                    continue;
                }

                // 3) Lấy message
                const msg = extractMsg(notif);
                if (!msg) continue;

                // 4) Chỉ xử lý sự kiện là tin nhắn mới
                if (!isNewMessageEvent(type, msg)) continue;

                // 5) Chuẩn hoá & quyết định phát âm
                const { authorId, partnerIds, isDiscussChannel } = normalizeMessage(msg);
                const me = selfPartnerId;

                // Không phát nếu mình là tác giả
                if (authorId && authorId === me) continue;

                // Discuss channel: recipients thường rỗng → chỉ cần khác tác giả là phát
                if (isDiscussChannel) {
                    playDefaultSound();
                    continue;
                }

                // Các loại khác: kiểm tra mình có trong người nhận
                if (partnerIds && partnerIds.includes(me)) {
                    playDefaultSound();
                }
            }
        });
    },
});
