/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
  Component,
  onWillStart,
  onMounted,
  onWillUnmount,
  useState,
  markup,
  useRef,
  useEffect,
} from "@odoo/owl";
import { makeCommunityAPI } from "@community_hub/client_action/api";
import { useEmojiPicker } from "@web/core/emoji_picker/emoji_picker";

console.log("[community_hub] app.js loaded ✅");

export class CommunityHubClientAction extends Component {
  static template = "community_hub.ClientAction";

  setup() {
    // services
    this.bus = this.env.services.bus_service;
    this.notification = this.env.services.notification;
    this.rpc = this.env.services.rpc;

    // attachment viewer (Odoo 17)
    this.attachmentViewer =
      this.env.services.attachment_viewer ||
      this.env.services["attachment_viewer"];

    this.router = this.env.services.router;

    this._deepLinkTimer = null;
    this._seenNoti = new Map();

    this._onHashChange = () => {
      const dl = this._getDeepLink();
      if (dl.communityId || dl.channelId || dl.postId || dl.tab) {
        clearTimeout(this._deepLinkTimer);
        this._deepLinkTimer = setTimeout(() => {
          this.loadBootstrap();
        }, 50);
      }
    };

    // api
    this.api = makeCommunityAPI(this.rpc);

    // refs
    this.postEditorRef = useRef("post_editor");
    this.postFileInputRef = useRef("post_files");
    this.commentFileInputRef = useRef("comment_files");
    this.editPostEditorRef = useRef("edit_post_editor");
    this.editCommentEditorRef = useRef("edit_comment_editor");
    this.emojiAnchorRef = useRef("emoji_anchor");

    // emoji context
    this._emojiCtx = { kind: null, postId: null, range: null };
    this._postSelRange = null;

    // emoji picker
    this._emojiPicker = useEmojiPicker(this.emojiAnchorRef, {
      onSelect: (emoji) => this._onEmojiSelected(emoji),
    });

    // ===== FIX CRITICAL: expose function for template =====
    // Template gọi ctx.commentCount(...) -> bắt buộc có function này trên instance.
    this.commentCount = (postOrId) => {
      let p = postOrId;
      if (typeof postOrId === "number") {
        p = this._getPostById(postOrId);
      }
      const n =
        p?.comment_count ??
        p?.comments_count ??
        p?.commentCount ??
        p?.comment_ids_count ??
        p?.message_count ??
        0;
      return Number(n || 0);
    };

    // internal bus tracking
    this._busStarted = false;
    this._unreadTimers = {};
    this._unreadInFlight = {};

    // state
    this.state = useState({
      loading: true,
      user: null,

      communities: [],
      selectedCommunity: null,

      channels: [],
      selectedChannelId: null,

      feed: [],
      feedOffset: 0,
      feedHasMore: false,

      openComments: {},

      preview: {
        open: false,
        att: null,
        text: null,
        loadingText: false,
        error: null,
      },

      ui: {
        activeTab: "posts",
        badges: {},
        channelBadges: {},

        searchQuery: "",
        communityQuery: "",
        channelQuery: "",

        composerMode: "post",
        announcementTitle: "",
        postHtml: "",
        postAttachments: [],
        postUploading: false,
        postEmojiOpen: false,

        commentDraft: {},
        commentHtml: {},
        commentAttachments: {},
        commentUploadTarget: null,
        commentUploading: false,
        commentEmojiOpen: false,
        commentEmojiTarget: null,

        postTextColor: "#111111",
        postBgColor: "#fff3a0",

        editPostId: null,
        editCommentId: null,
        editCommentPostId: null,

        showNewCommunity: false,
        newCommunityName: "",
        newCommunityPublic: false,
        newCommunityPolicy: "invite",

        showNewChannel: false,
        newChannelName: "",

        settingsOpen: false,
        settingsTab: "members",
        myRole: null,
        members: [],
        memberQuery: "",
        memberResults: [],

        communityForm: {
          name: "",
          join_policy: "invite",
          is_public: false,
          description_html: "",
        },
        channelForm: { name: "", sequence: 10 },
      },
    });

    // ========= BUS NOTIFICATION HANDLER =========
    this._onBusNotification = (ev) => {
      const raw = ev?.detail;
      const list = Array.isArray(raw)
        ? raw
        : Array.isArray(raw?.notifications)
          ? raw.notifications
          : [];

      for (const n of list) {
        const payload = Array.isArray(n)
          ? n[1]
          : (n?.payload ?? n?.message ?? n);
        if (!payload?.type) continue;

        if (payload.type === "bootstrap_reload") {
          this.loadBootstrap();
          continue;
        }

        if (payload.type === "invited") {
          this.notification.add(
            `Bạn được mời vào community: ${payload.community_name || payload.community_id}`,
            { type: "info" }
          );
          this.loadBootstrap();
          continue;
        }

        if (payload.type === "kicked") {
          this.notification.add(
            `Bạn đã bị kick khỏi community #${payload.community_id}`,
            { type: "warning" }
          );
          this.loadBootstrap();
          continue;
        }

        if (payload.type === "notify_post") {
          this._scheduleUnreadRefresh(payload.community_id);
          this._desktopNotify(payload);
          continue;
        }

        if (payload.type === "notify_comment") {
          this._scheduleUnreadRefresh(payload.community_id);
          this._desktopNotify(payload);
          continue;
        }
      }
    };

    onWillStart(async () => {
      await this.loadBootstrap();
    });

    onMounted(() => {
      if (!this._busStarted) {
        this._busStarted = true;
        this.bus.addEventListener("notification", this._onBusNotification);
        this._syncBusChannels();
        this.bus.start();
      } else {
        this._syncBusChannels();
      }
      window.addEventListener("hashchange", this._onHashChange);
    });

    onWillUnmount(() => {
      if (this._busStarted) {
        this.bus.removeEventListener("notification", this._onBusNotification);
      }
      window.removeEventListener("hashchange", this._onHashChange);
      clearTimeout(this._deepLinkTimer);
      this._deepLinkTimer = null;
    });

    useEffect(
      () => this._syncBusChannels(),
      () => [this.state.user?.id]
    );
  }

  // ---------- helpers ----------
  _isUrl(att) {
    return att?.type === "url" && !!att?.url;
  }

  _contentUrl(att, download = false) {
    if (!att) return "";
    if (att.open_url && !download) return att.open_url;
    if (att.download_url && download) return att.download_url;
    if (att.url) return att.url;
    if (att.id) return `/web/content/${att.id}?download=${download ? "true" : "false"}`;
    return "";
  }

  _downloadUrl(att) {
    return this._contentUrl(att, true);
  }

  _m(att) {
    return (att?.mimetype || "").toLowerCase();
  }
  _isImage(att) {
    return this._m(att).startsWith("image/");
  }
  _isPdf(att) {
    return this._m(att) === "application/pdf";
  }
  _isVideo(att) {
    return this._m(att).startsWith("video/");
  }
  _isAudio(att) {
    return this._m(att).startsWith("audio/");
  }
  _isText(att) {
    const m = this._m(att);
    return m.startsWith("text/") || m === "application/json" || m === "application/xml";
  }

  _formatBytes(bytes) {
    const n = Number(bytes || 0);
    if (!n) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let i = 0, v = n;
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i++;
    }
    return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
  }

  _shouldSkipNoti(key, ttlMs = 2500) {
    const now = Date.now();
    const last = this._seenNoti.get(key) || 0;
    if (now - last < ttlMs) return true;
    this._seenNoti.set(key, now);
    return false;
  }

  _desktopNotify(payload) {
    if (!document.hidden) return;
    const url = payload?.open_url || payload?.url;
    if (!url) return;

    const key =
      payload?.dedupe_key ||
      `${payload?.type || "x"}:${payload?.community_id || 0}:${payload?.channel_id || 0}:${payload?.post_id || 0}:${payload?.comment_id || 0}`;
    if (this._shouldSkipNoti(key)) return;

    if (Notification.permission === "default") {
      Notification.requestPermission();
    }
    if (Notification.permission !== "granted") return;

    const n = new Notification(payload.title || "Community Hub", {
      body: payload.body || payload.message || "",
    });

    n.onclick = () => {
      try { window.focus(); } catch (e) {}
      window.location.assign(url);
      try { n.close(); } catch (e) {}
    };
  }

  // =========================================================
  // Attachment Viewer
  // =========================================================
  _viewerNormalizeList(list) {
    const arr = Array.isArray(list) ? list : list ? [list] : [];
    return arr
      .filter((a) => a && !this._isUrl(a) && !!a.id)
      .map((a) => ({ id: a.id, name: a.name, mimetype: a.mimetype }));
  }

  _openAttachmentViewer(list, activeId) {
    const attachments = this._viewerNormalizeList(list);
    const id = Number(activeId || attachments?.[0]?.id || 0);
    if (!attachments.length || !id) return false;

    try {
      if (this.attachmentViewer?.open) {
        this.attachmentViewer.open({
          attachments,
          activeAttachmentID: id,
        });
        return true;
      }
    } catch (e) {}

    try {
      if (this.attachmentViewer?.open) {
        this.attachmentViewer.open(attachments, id);
        return true;
      }
    } catch (e) {}

    return false;
  }

  async openPreview(att) {
    if (!att) return;

    if (this._isUrl(att)) {
      window.open(att.url, "_blank", "noopener");
      return;
    }

    this.state.preview.open = true;
    this.state.preview.att = att;
    this.state.preview.text = null;
    this.state.preview.loadingText = false;
    this.state.preview.error = null;

    if (this._isText(att)) {
      this.state.preview.loadingText = true;
      try {
        const r = await fetch(this._contentUrl(att, false), {
          credentials: "same-origin",
        });
        const blob = await r.blob();
        const text = await blob.text();
        this.state.preview.text = text.slice(0, 200000);
      } catch (e) {
        this.state.preview.error = e?.message || String(e);
      } finally {
        this.state.preview.loadingText = false;
      }
    }
  }

  closePreview() {
    this.state.preview.open = false;
    this.state.preview.att = null;
    this.state.preview.text = null;
    this.state.preview.loadingText = false;
    this.state.preview.error = null;
  }

  // ========= GETTERS =========
  get isJoined() {
    return this.state.selectedCommunity?.my_state === "joined";
  }

  get canManage() {
    return ["owner", "admin"].includes(this.state.ui.myRole);
  }

  get selectedChannel() {
    return (
      this.state.channels.find((c) => c.id === this.state.selectedChannelId) || null
    );
  }

  get canSubmitPost() {
    const html = (this.state.ui.postHtml || "").trim();
    const hasText = this._stripHtml(html).trim().length > 0;
    const hasAtt = (this.state.ui.postAttachments || []).length > 0;
    return hasText || hasAtt;
  }

  // ========= SEARCH =========
  get searchQuery() {
    return (this.state.ui.searchQuery || "").trim();
  }
  get hasSearch() {
    return this.searchQuery.length > 0;
  }
  get searchPlaceholder() {
    switch (this.state.ui.activeTab) {
      case "posts":
        return "Tìm bài viết / bình luận / file đính kèm...";
      case "files":
        return "Tìm tập tin (tên file, người gửi)...";
      case "photos":
        return "Tìm ảnh (tên ảnh nếu có, người gửi)...";
      default:
        return "Tìm kiếm...";
    }
  }
  onSearchInput(ev) {
    this.state.ui.searchQuery = ev?.target?.value || "";
  }
  onSearchKeydown(ev) {
    if (ev.key === "Escape") this.clearSearch();
  }
  clearSearch() {
    this.state.ui.searchQuery = "";
  }

  _normText(s) {
    return String(s || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }
  _match(q, hay) {
    const nq = this._normText(q);
    if (!nq) return true;
    return this._normText(hay).includes(nq);
  }

  // ===================== FILES/PHOTOS FLATTEN =====================
  get flattenFiles() {
    const out = [];
    const feed = this.state.feed || [];

    for (const p of feed) {
      for (const a of p.attachments || []) {
        out.push({
          key: `post:${p.id}-a${a.id}`,
          id: a.id,
          name: a.name,
          url: a.download_url || a.open_url || a.url,
          open_url: a.open_url || a.view_url || a.url,
          download_url: a.download_url || a.url,
          mimetype: a.mimetype,
          size: a.size || a.file_size || 0,
          from: `${p.author_name || ""}`,
          post_id: p.id,
          create_date: a.create_date || p.create_date || null,
        });
      }
    }

    const oc = this.state.openComments || {};
    for (const postIdStr of Object.keys(oc)) {
      const th = oc[postIdStr];
      if (!th?.loaded) continue;
      for (const c of th.items || []) {
        for (const a of c.attachments || []) {
          out.push({
            key: `cmt:${c.id}-a${a.id}`,
            id: a.id,
            name: a.name,
            url: a.download_url || a.open_url || a.url,
            open_url: a.open_url || a.view_url || a.url,
            download_url: a.download_url || a.url,
            mimetype: a.mimetype,
            size: a.size || a.file_size || 0,
            from: `${c.author_name || ""}`,
            post_id: c.post_id || parseInt(postIdStr, 10) || null,
            create_date: a.create_date || c.create_date || null,
          });
        }
      }
    }

    return out;
  }

  get flattenPhotos() {
    const out = [];
    const feed = this.state.feed || [];

    for (const p of feed) {
      for (const a of p.attachments || []) {
        if ((a.mimetype || "").startsWith("image/")) {
          out.push({
            key: `post:${p.id}-a${a.id}`,
            id: a.id,
            name: a.name || "",
            url: a.open_url || a.url,
            open_url: a.open_url || a.url,
            mimetype: a.mimetype,
            from: `${p.author_name || ""}`,
            post_id: p.id,
            create_date: a.create_date || p.create_date || null,
          });
        }
      }
    }

    const oc = this.state.openComments || {};
    for (const postIdStr of Object.keys(oc)) {
      const th = oc[postIdStr];
      if (!th?.loaded) continue;
      for (const c of th.items || []) {
        for (const a of c.attachments || []) {
          if ((a.mimetype || "").startsWith("image/")) {
            out.push({
              key: `cmt:${c.id}-a${a.id}`,
              id: a.id,
              name: a.name || "",
              url: a.open_url || a.url,
              open_url: a.open_url || a.url,
              mimetype: a.mimetype,
              from: `${c.author_name || ""}`,
              post_id: c.post_id || parseInt(postIdStr, 10) || null,
              create_date: a.create_date || c.create_date || null,
            });
          }
        }
      }
    }

    return out;
  }

  // ===================== EMOJI PICKER =====================
  _emojiToChar(e) {
    if (!e) return "";
    if (typeof e === "string") return e;
    return e.emoji || e.unicode || e.char || e.native || e.value || e.code || "";
  }

  _captureRange(editorEl) {
    try {
      if (!editorEl) return null;
      const sel = window.getSelection();
      if (!sel || sel.rangeCount === 0) return null;
      const r = sel.getRangeAt(0);
      const node = r.commonAncestorContainer;
      if (editorEl.contains(node)) return r.cloneRange();
    } catch (_) {}
    return null;
  }

  _restoreRange(range) {
    try {
      if (!range) return false;
      const sel = window.getSelection();
      if (!sel) return false;
      sel.removeAllRanges();
      sel.addRange(range);
      return true;
    } catch (_) {}
    return false;
  }

  _insertTextAtCaret(editorEl, text) {
    if (!editorEl || !text) return;
    editorEl.focus?.();

    const sel = window.getSelection();
    if (sel && sel.rangeCount) {
      const range = sel.getRangeAt(0);
      range.deleteContents();
      range.insertNode(document.createTextNode(text));
      range.collapse(false);
      sel.removeAllRanges();
      sel.addRange(range);
      return;
    }

    try {
      document.execCommand("insertText", false, text);
    } catch (_) {
      editorEl.innerHTML = (editorEl.innerHTML || "") + text;
    }
  }

  _positionEmojiAnchorNear(el) {
    const anchor = this.emojiAnchorRef?.el;
    if (!anchor || !el) return;

    const rect = el.getBoundingClientRect();
    anchor.style.position = "fixed";
    anchor.style.left = `${Math.round(rect.left)}px`;
    anchor.style.top = `${Math.round(rect.bottom)}px`;
    anchor.style.width = "1px";
    anchor.style.height = "1px";
    anchor.style.pointerEvents = "auto";
    anchor.style.zIndex = "9999";
  }

  _openEmojiPicker(ev, ctx) {
    const btn = ev?.currentTarget;
    const editorEl = ctx?.editorEl;

    this._emojiCtx.kind = ctx?.kind || null;
    this._emojiCtx.postId = ctx?.postId || null;
    this._emojiCtx.range = this._captureRange(editorEl);

    if (btn) this._positionEmojiAnchorNear(btn);

    const anchor = this.emojiAnchorRef?.el;
    if (anchor) {
      anchor.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    }
  }

  _onEmojiSelected(raw) {
    const ch = this._emojiToChar(raw);
    if (!ch) return;

    let editorEl = null;
    if (this._emojiCtx.kind === "post") {
      editorEl = this.postEditorRef?.el;
    } else if (this._emojiCtx.kind === "comment") {
      editorEl = this._findCommentEditor(this._emojiCtx.postId);
    }
    if (!editorEl) return;

    this._restoreRange(this._emojiCtx.range);
    this._insertTextAtCaret(editorEl, ch);

    if (this._emojiCtx.kind === "post") {
      this.state.ui.postHtml = editorEl.innerHTML || "";
    } else if (this._emojiCtx.kind === "comment") {
      const pid = this._emojiCtx.postId;
      if (pid) this.state.ui.commentHtml[pid] = editorEl.innerHTML || "";
    }

    this._emojiCtx.kind = null;
    this._emojiCtx.postId = null;
    this._emojiCtx.range = null;
  }

  // ========= UTIL =========
  _stripHtml(html) {
    const div = document.createElement("div");
    div.innerHTML = html || "";
    return div.textContent || div.innerText || "";
  }

  _avatarText(name) {
    const s = (name || "").trim();
    if (!s) return "?";
    const parts = s.split(/\s+/).slice(0, 2);
    return parts.map((p) => (p[0] || "").toUpperCase()).join("");
  }

  _parseDate(v) {
    if (!v) return null;
    if (v instanceof Date) return isNaN(v.getTime()) ? null : v;

    let s = String(v).trim();
    if (!s) return null;

    s = s.replace(" ", "T");
    s = s.replace(/\.(\d{3})\d+/, ".$1");

    const hasTz = /([zZ]|[+\-]\d{2}:?\d{2})$/.test(s);
    const isPlain = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?$/.test(s);
    if (isPlain && !hasTz) s = `${s}Z`;

    const d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }

  _pad2(n) {
    return String(n).padStart(2, "0");
  }

  _formatDateOnly(dt) {
    const d = this._parseDate(dt);
    if (!d) return "";
    return `${this._pad2(d.getDate())}/${this._pad2(d.getMonth() + 1)}/${d.getFullYear()}`;
  }

  _dateText(dt) {
    const d = this._parseDate(dt);
    if (!d) {
      const s = dt ? String(dt) : "";
      return s ? s.replace("T", " ").slice(0, 16) : "";
    }
    const y = d.getFullYear();
    const m = this._pad2(d.getMonth() + 1);
    const day = this._pad2(d.getDate());
    const hh = this._pad2(d.getHours());
    const mm = this._pad2(d.getMinutes());
    return `${y}-${m}-${day} ${hh}:${mm}`;
  }

  // ========= BUS CHANNELS =========
  _syncBusChannels() {
    if (!this._busStarted) return;

    if (this.state.user?.id) {
      try {
        this.bus.addChannel("community_hub.user", this.state.user.id);
      } catch (e) {}
    }
  }

  // ========= ATTACHMENT HELPERS =========
  _humanSize(bytes) {
    const n = Number(bytes || 0);
    if (!n) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let i = 0;
    let v = n;
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i++;
    }
    const fixed = v >= 10 || i === 0 ? 0 : 1;
    return `${v.toFixed(fixed)} ${units[i]}`;
  }

  _guessKind(att) {
    const mt = (att?.mimetype || "").toLowerCase();
    const ext = (att?.ext || (att?.name || "").split(".").pop() || "").toLowerCase();

    if (mt.startsWith("image/")) return "image";
    if (mt.includes("pdf") || ext === "pdf") return "pdf";
    if (mt.includes("spreadsheet") || ["xls", "xlsx", "ods", "csv"].includes(ext)) return "sheet";
    if (mt.includes("word") || ["doc", "docx", "odt"].includes(ext)) return "doc";
    if (mt.includes("presentation") || ["ppt", "pptx", "odp"].includes(ext)) return "slide";
    if (mt.startsWith("video/")) return "video";
    if (mt.startsWith("audio/")) return "audio";
    if (["zip", "rar", "7z", "tar", "gz"].includes(ext)) return "archive";
    return "file";
  }

  _iconText(kind) {
    switch (kind) {
      case "image":
        return "🖼";
      case "pdf":
        return "PDF";
      case "sheet":
        return "XLS";
      case "doc":
        return "DOC";
      case "slide":
        return "PPT";
      case "video":
        return "VID";
      case "audio":
        return "AUD";
      case "archive":
        return "ZIP";
      default:
        return "FILE";
    }
  }

  _normalizeAttachment(a) {
    if (!a) return null;
    const kind = this._guessKind(a);
    const ext = (a.ext || (a.name || "").split(".").pop() || "").toLowerCase();

    const openUrl =
      a.open_url ||
      a.view_url ||
      a.url ||
      (a.id ? `/web/content/${a.id}?download=false` : "");

    const downloadUrl =
      a.download_url || (a.id ? `/web/content/${a.id}?download=true` : openUrl);

    const extText = (ext || kind || "").toUpperCase();

    return {
      ...a,
      ext,
      extText,
      kind,
      iconText: this._iconText(kind),
      sizeText: this._humanSize(a.size || a.file_size || 0),
      open_url: openUrl,
      download_url: downloadUrl,
      thumb_url: a.thumb_url || (kind === "image" ? openUrl : ""),
    };
  }

  // ===== Reactive helpers =====
  _setBadges(next) {
    this.state.ui.badges = next || {};
  }
  _bumpBadge(cid) {
    if (!cid) return;
    const cur = this.state.ui.badges || {};
    this._setBadges({ ...cur, [cid]: (cur[cid] || 0) + 1 });
  }
  _applyUnreadPayload(unread, { merge = false } = {}) {
    const u = unread || {};

    if (u.community) {
      const incoming = {};
      for (const [k, v] of Object.entries(u.community || {})) {
        incoming[Number(k)] = Number(v || 0);
      }
      const next = merge ? { ...(this.state.ui.badges || {}), ...incoming } : incoming;
      this._setBadges(next);
    }

    if (u.channel) {
      const incoming = {};
      for (const [k, v] of Object.entries(u.channel || {})) {
        incoming[Number(k)] = Number(v || 0);
      }
      this.state.ui.channelBadges = merge
        ? { ...(this.state.ui.channelBadges || {}), ...incoming }
        : incoming;
    }
  }

  getCommunityUnread(communityId) {
    const cid = Number(communityId || 0);
    if (!cid) return 0;
    const v = this.state.ui?.badges?.[cid] ?? this.state.ui?.badges?.[String(cid)] ?? 0;
    return Number(v || 0);
  }

  getChannelUnread(channelId) {
    const chid = Number(channelId || 0);
    if (!chid) return 0;
    const v =
      this.state.ui?.channelBadges?.[chid] ??
      this.state.ui?.channelBadges?.[String(chid)] ??
      0;
    return Number(v || 0);
  }

  formatUnread(n) {
    const x = Number(n || 0);
    if (!x) return "";
    return x > 99 ? "99+" : String(x);
  }

  _scheduleUnreadRefresh(communityId) {
    const cid = Number(communityId || 0);
    if (!cid) return;

    clearTimeout(this._unreadTimers[cid]);
    this._unreadTimers[cid] = setTimeout(async () => {
      try {
        if (this._unreadInFlight[cid]) return;
        this._unreadInFlight[cid] = true;

        if (typeof this.api?.unread === "function") {
          const res = await this.api.unread({ communityId: cid });
          this._applyUnreadPayload(res?.unread, { merge: true });
        } else {
          this._bumpBadge(cid);
        }
      } finally {
        this._unreadInFlight[cid] = false;
      }
    }, 150);
  }

  async markReadCurrentChannel(latestPostId = null) {
    const channelId = Number(this.state.selectedChannelId || 0);
    if (!channelId) return;
    if (typeof this.api?.markChannelRead !== "function") return;

    try {
      const res = await this.api.markChannelRead({
        channelId,
        lastPostId: latestPostId || null,
      });
      if (res?.unread) {
        this._applyUnreadPayload(res.unread, { merge: true });
      }
    } catch (e) {}
  }

  _setOpenComments(next) {
    this.state.openComments = next || {};
  }
  _openCommentsUpsert(postId, val) {
    const cur = this.state.openComments || {};
    this._setOpenComments({ ...cur, [postId]: val });
  }
  _openCommentsRemove(postId) {
    const cur = this.state.openComments || {};
    if (!(postId in cur)) return;
    const next = { ...cur };
    delete next[postId];
    this._setOpenComments(next);
  }

  // ========= PERMISSIONS =========
  _canEditPost(p) {
    const myId = this.state.user?.id;
    if (!myId) return false;
    return p?.create_uid === myId;
  }
  _canEditComment(c) {
    const myId = this.state.user?.id;
    if (!myId) return false;
    return c?.create_uid === myId;
  }

  // ========= SEARCH: POSTS/COMMENTS =========
  _postHay(p) {
    const body = this._stripHtml(p?.body_html || "");
    const atts = (p?.attachments || []).map((a) => a?.name || "").join(" ");
    const author = p?.author_name || "";
    return `${author} ${body} ${atts}`;
  }
  _commentHay(c) {
    const body = this._stripHtml(c?.body_html || "");
    const atts = (c?.attachments || []).map((a) => a?.name || "").join(" ");
    const author = c?.author_name || "";
    return `${author} ${body} ${atts}`;
  }
  _postMatches(p, q) {
    return this._match(q, this._postHay(p));
  }
  _threadHasMatch(postId, q) {
    const th = (this.state.openComments || {})[postId];
    if (!th?.loaded) return false;
    const items = th.items || [];
    return items.some((c) => this._match(q, this._commentHay(c)));
  }

  get filteredFeed() {
    const list = this.state.feed || [];
    if (!this.hasSearch) return list;

    const q = this.searchQuery;
    return list.filter((p) => this._postMatches(p, q) || this._threadHasMatch(p.id, q));
  }

  getVisibleComments(postId) {
    const th = (this.state.openComments || {})[postId];
    if (!th?.loaded) return th?.items || [];

    const items = th.items || [];
    if (!this.hasSearch) return items;

    const q = this.searchQuery;
    return items.filter((c) => this._match(q, this._commentHay(c)));
  }

  _fileHay(f) {
    return `${f?.name || ""} ${f?.from || ""}`;
  }
  _photoHay(p) {
    return `${p?.name || ""} ${p?.from || ""}`;
  }

  // ===================== TIMELINE HELPERS =====================
  _dateKeyFromAny(v) {
    const d = this._parseDate(v);
    if (!d) return null;
    const y = d.getFullYear();
    const m = this._pad2(d.getMonth() + 1);
    const day = this._pad2(d.getDate());
    return `${y}-${m}-${day}`;
  }

  _groupTitleFromKey(key) {
    if (!key) return "Không rõ ngày";
    const d = this._parseDate(`${key}T00:00:00Z`);
    if (!d) return key;

    const today = new Date();
    const t0 = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const d0 = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const diffDays = Math.round((t0 - d0) / 86400000);

    const ddmmyyyy = this._formatDateOnly(d);
    if (diffDays === 0) return `Hôm nay • ${ddmmyyyy}`;
    if (diffDays === 1) return `Hôm qua • ${ddmmyyyy}`;
    return ddmmyyyy;
  }

  _guessISO(item) {
    return (
      item?.create_date ||
      item?.createDate ||
      item?.dateISO ||
      item?.created_at ||
      item?.createdAt ||
      null
    );
  }

  _buildTimeline(list) {
    const map = new Map();

    for (const it of list || []) {
      const iso = this._guessISO(it);
      const key = this._dateKeyFromAny(iso) || "unknown";
      if (!map.has(key)) map.set(key, []);
      map.get(key).push({ ...it, __iso: iso });
    }

    const keys = Array.from(map.keys()).sort((a, b) => {
      if (a === "unknown") return 1;
      if (b === "unknown") return -1;
      return b.localeCompare(a);
    });

    return keys.map((k) => {
      const items = map.get(k) || [];
      items.sort((a, b) => {
        const ta = this._parseDate(a.__iso)?.getTime?.() || 0;
        const tb = this._parseDate(b.__iso)?.getTime?.() || 0;
        return tb - ta;
      });

      return {
        key: k,
        title: k === "unknown" ? "Không rõ ngày" : this._groupTitleFromKey(k),
        items,
      };
    });
  }

  get filesTimeline() {
    return this._buildTimeline(this.flattenFiles || []);
  }
  get photosTimeline() {
    return this._buildTimeline(this.flattenPhotos || []);
  }
  get filesTimelineView() {
    if (!this.hasSearch) return this.filesTimeline;
    const q = this.searchQuery;
    const filtered = (this.flattenFiles || []).filter((f) => this._match(q, this._fileHay(f)));
    return this._buildTimeline(filtered);
  }
  get photosTimelineView() {
    if (!this.hasSearch) return this.photosTimeline;
    const q = this.searchQuery;
    const filtered = (this.flattenPhotos || []).filter((p) => this._match(q, this._photoHay(p)));
    return this._buildTimeline(filtered);
  }

  // ===================== DEEPLINK =====================
  _getDeepLink() {
    const ap = this.props?.action?.params || {};
    const fromAction = {
      communityId: Number(ap.community_id || ap.communityId || 0) || 0,
      channelId: Number(ap.channel_id || ap.channelId || 0) || 0,
      postId: Number(ap.post_id || ap.postId || 0) || 0,
      tab: ap.tab || null,
    };

    const rawHash = (this._getHashString() || "").replace(/^#/, "");
    const hp = new URLSearchParams(rawHash);
    const fromHash = {
      communityId: this._getParamNumber(hp, "community_id", "communityId"),
      channelId: this._getParamNumber(hp, "channel_id", "channelId"),
      postId: this._getParamNumber(hp, "post_id", "postId"),
      tab: hp.get("tab") || null,
    };

    const sp = new URLSearchParams(window.location.search || "");
    const fromSearch = {
      communityId: this._getParamNumber(sp, "community_id", "communityId"),
      channelId: this._getParamNumber(sp, "channel_id", "channelId"),
      postId: this._getParamNumber(sp, "post_id", "postId"),
      tab: sp.get("tab") || null,
    };

    const out = {
      communityId: fromAction.communityId || fromHash.communityId || fromSearch.communityId,
      channelId: fromAction.channelId || fromHash.channelId || fromSearch.channelId,
      postId: fromAction.postId || fromHash.postId || fromSearch.postId,
      tab: fromAction.tab || fromHash.tab || fromSearch.tab,
    };

    console.log("[community_hub] deepLink =", out, "hash=", window.location.hash);
    return out;
  }

  _getHashString() {
    const h = window.location.hash;
    if (typeof h === "string" && h) return h;

    const raw = this.env?.services?.router?.current?.hash;
    if (typeof raw === "string") return raw;
    return String(raw || "");
  }

  _getParamNumber(params, ...keys) {
    for (const k of keys) {
      const v = params.get(k);
      if (v !== null && v !== undefined && String(v).trim() !== "") {
        const n = Number(v);
        if (!Number.isNaN(n) && n) return n;
      }
    }
    return 0;
  }

  // ========= BOOTSTRAP =========
  async loadBootstrap() {
    const resetThreadsAndFeed = () => {
      this.state.channels = [];
      this.state.selectedChannelId = null;

      this.state.feed = [];
      this.state.feedOffset = 0;
      this.state.feedHasMore = false;

      this._setOpenComments({});
      this._resetComposerAll();

      this.state.ui.editPostId = null;
      this.state.ui.editCommentId = null;
      this.state.ui.editCommentPostId = null;
    };

    const tryScrollToPost = (postId, tries = 16) => {
      if (!postId) return;

      const attempt = () => {
        const el = this.el?.querySelector?.(`[data-post-id="${postId}"]`);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
          return;
        }
        if (tries > 0) {
          tries -= 1;
          setTimeout(attempt, 80);
        }
      };
      setTimeout(attempt, 0);
    };

    const prevCommunityId = this.state.selectedCommunity?.id || 0;
    const prevChannelId = this.state.selectedChannelId || 0;

    try {
      this.state.loading = true;

      const dl = this._getDeepLink();
      const data = await this.api.bootstrap();

      this._applyUnreadPayload(data.unread, { merge: false });

      this.state.user = data.user || null;
      this.state.communities = data.communities || [];

      let selected = data.selected || null;

      if (dl.communityId) {
        const byLink = (this.state.communities || []).find((c) => c.id === dl.communityId);
        if (byLink) selected = byLink;
      } else if (prevCommunityId) {
        const byPrev = (this.state.communities || []).find((c) => c.id === prevCommunityId);
        if (byPrev) selected = byPrev;
      }

      this.state.selectedCommunity = selected;

      if (!this.state.selectedCommunity || !this.state.communities.length) {
        resetThreadsAndFeed();
        this.state.ui.myRole = null;
        this.state.ui.settingsOpen = false;

        if (dl.tab) this.state.ui.activeTab = dl.tab;

        this.state.loading = false;
        return;
      }

      if (this.state.selectedCommunity.my_state !== "joined") {
        resetThreadsAndFeed();
        this.state.ui.myRole = this.state.selectedCommunity?.my_role || null;
        this.state.ui.settingsOpen = false;

        if (dl.communityId || dl.channelId || dl.postId) {
          this.state.ui.activeTab = dl.tab || "posts";
        } else if (dl.tab) {
          this.state.ui.activeTab = dl.tab;
        }

        this.state.loading = false;
        return;
      }

      if (dl.communityId || dl.channelId || dl.postId) {
        this.state.ui.activeTab = dl.tab || "posts";
      } else if (dl.tab) {
        this.state.ui.activeTab = dl.tab;
      }

      let channels = data.channels || [];
      const selId = this.state.selectedCommunity?.id || 0;
      const bootSelId = data.selected?.id || 0;

      if (selId && selId !== bootSelId && typeof this.api.channels === "function") {
        try {
          const resCh = await this.api.channels(selId);
          channels = resCh.items || [];
        } catch (_) {}
      }

      this.state.channels = channels;

      let nextChannelId = null;

      if (dl.channelId && channels.some((c) => Number(c.id) === Number(dl.channelId))) {
        nextChannelId = dl.channelId;
      } else if (prevChannelId && channels.some((c) => c.id === prevChannelId)) {
        nextChannelId = prevChannelId;
      } else {
        nextChannelId = channels[0]?.id || null;
      }

      this.state.selectedChannelId = nextChannelId;

      this.state.feed = [];
      this.state.feedOffset = 0;
      this.state.feedHasMore = false;
      this._setOpenComments({});

      this.state.ui.settingsOpen = false;
      this.state.ui.myRole = this.state.selectedCommunity?.my_role || null;

      this.state.ui.editPostId = null;
      this.state.ui.editCommentId = null;
      this.state.ui.editCommentPostId = null;

      this._resetComposerAll();

      this.state.loading = false;

      if (this.state.selectedChannelId) {
        await this.refreshFeed();
        if (dl.postId) tryScrollToPost(dl.postId);
      }
    } catch (e) {
      this.state.loading = false;
      this.notification.add(`Bootstrap error: ${e?.message || e}`, { type: "danger" });
    }
  }

  _resetComposerAll() {
    this.state.ui.postHtml = "";
    this.state.ui.postAttachments = [];
    this.state.ui.postUploading = false;
    this.state.ui.postEmojiOpen = false;
    if (this.postEditorRef?.el) this.postEditorRef.el.innerHTML = "";

    this.state.ui.commentDraft = {};
    this.state.ui.commentHtml = {};
    this.state.ui.commentAttachments = {};
    this.state.ui.commentUploadTarget = null;
    this.state.ui.commentUploading = false;
    this.state.ui.commentEmojiOpen = false;
    this.state.ui.commentEmojiTarget = null;
  }

  // ========= SELECT COMMUNITY / CHANNEL =========
  async selectCommunity(ev) {
    const id = parseInt(ev.currentTarget?.dataset?.communityId || "0", 10);
    if (!id) return;

    const c = this.state.communities.find((x) => x.id === id);
    if (!c) return;

    this.state.selectedCommunity = c;
    this.state.ui.settingsOpen = false;
    this.state.ui.myRole = c.my_role || null;

    if (c.my_state !== "joined") {
      this.state.channels = [];
      this.state.selectedChannelId = null;
      this.state.feed = [];
      this.state.feedOffset = 0;
      this.state.feedHasMore = false;
      this._setOpenComments({});
      this._resetComposerAll();
      return;
    }

    await this.reloadChannels();

    this.state.selectedChannelId = this.state.channels[0]?.id || null;
    this.state.feed = [];
    this.state.feedOffset = 0;
    this.state.feedHasMore = false;
    this._setOpenComments({});
    this._resetComposerAll();

    if (this.state.selectedChannelId) {
      await this.refreshFeed();
      this._scheduleUnreadRefresh(c.id);
    }
  }

  async selectChannel(ev) {
    const id = parseInt(ev.currentTarget?.dataset?.channelId || "0", 10);
    if (!id) return;

    this.state.selectedChannelId = id;
    this.state.feed = [];
    this.state.feedOffset = 0;
    this.state.feedHasMore = false;
    this._setOpenComments({});
    this._resetComposerAll();

    await this.refreshFeed();
  }

  async reloadChannels() {
    const cid = this.state.selectedCommunity?.id;
    if (!cid) {
      this.state.channels = [];
      this.state.selectedChannelId = null;
      return;
    }
    const res = await this.api.channels(cid);
    this.state.channels = res.items || [];
    if (!this.state.channels.some((c) => c.id === this.state.selectedChannelId)) {
      this.state.selectedChannelId = this.state.channels[0]?.id || null;
    }
  }

  // ========= FEED =========
  async refreshFeed() {
    if (!this.isJoined) return;
    if (!this.state.selectedChannelId) return;

    try {
      const res = await this.api.feed(this.state.selectedChannelId, { limit: 20, offset: 0 });
      const comm = this.state.selectedCommunity;

      const items = (res.items || []).map((p) => ({
        ...p,
        is_owner: comm?.owner_id && p.author_id === comm.owner_id,
        avatarText: this._avatarText(p.author_name),
        dateText: this._dateText(p.create_date),
        body: markup(p.body_html || ""),
        attachments: (p.attachments || [])
          .map((a) => this._normalizeAttachment({ ...a, post_id: p.id }))
          .filter(Boolean),
        reactions: p.reactions || [],
      }));

      this.state.feed = items;
      this.state.feedOffset = items.length;
      this.state.feedHasMore = !!res.has_more;

      const latestId = items?.[0]?.id || null;
      await this.markReadCurrentChannel(latestId);

      this._scheduleUnreadRefresh(this.state.selectedCommunity?.id);
    } catch (e) {
      this.notification.add("Không thể tải feed (có thể bạn không còn quyền).", {
        type: "warning",
      });
      await this.loadBootstrap();
    }
  }

  async loadMore() {
    if (!this.state.selectedChannelId || !this.state.feedHasMore) return;

    const res = await this.api.feed(this.state.selectedChannelId, {
      limit: 20,
      offset: this.state.feedOffset,
    });
    const comm = this.state.selectedCommunity;

    const items = (res.items || []).map((p) => ({
      ...p,
      is_owner: comm?.owner_id && p.author_id === comm.owner_id,
      avatarText: this._avatarText(p.author_name),
      dateText: this._dateText(p.create_date),
      body: markup(p.body_html || ""),
      attachments: (p.attachments || [])
        .map((a) => this._normalizeAttachment({ ...a, post_id: p.id }))
        .filter(Boolean),
      reactions: p.reactions || [],
    }));

    this.state.feed.push(...items);
    this.state.feedOffset += items.length;
    this.state.feedHasMore = !!res.has_more;
  }

  // ========= TABS / COMPOSER MODE =========
  onTabClick(ev) {
    const tab = ev.currentTarget?.dataset?.tab;
    if (tab) this.state.ui.activeTab = tab;
  }

  onComposerModeClick(ev) {
    const mode = ev.currentTarget?.dataset?.mode;
    if (mode) this.state.ui.composerMode = mode;
  }

  // ========= POST EDITOR =========
  onPostEditorInput(ev) {
    this.state.ui.postHtml = ev.currentTarget?.innerHTML || "";
    this._postSelRange = this._captureRange(this.postEditorRef?.el);
  }

  onPostCmdClick(ev) {
    const cmd = ev.currentTarget?.dataset?.cmd;
    if (!cmd) return;

    const ed = this.postEditorRef?.el;
    ed?.focus?.();

    if (this._postSelRange) this._restoreRange(this._postSelRange);

    if (cmd === "createLink") {
      const url = window.prompt("Nhập link (https://...):");
      if (url) document.execCommand("createLink", false, url);
    } else {
      document.execCommand(cmd, false, null);
    }

    this.state.ui.postHtml = ed?.innerHTML || "";
    this._postSelRange = this._captureRange(ed);
  }

  togglePostEmoji(ev) {
    this._openEmojiPicker(ev, {
      kind: "post",
      postId: null,
      editorEl: this.postEditorRef?.el,
    });
    this.state.ui.postEmojiOpen = false;
  }

  onInsertPostEmoji(ev) {
    const emoji = ev.currentTarget?.dataset?.emoji;
    if (!emoji) return;

    this.postEditorRef?.el?.focus?.();
    document.execCommand("insertText", false, emoji);
    this.state.ui.postHtml = this.postEditorRef?.el?.innerHTML || "";
    this._postSelRange = this._captureRange(this.postEditorRef?.el);
  }

  // ========= POST ATTACHMENTS =========
  onPostAttachClick() {
    if (!this.isJoined) return;
    this.postFileInputRef?.el?.click?.();
  }

  async onPostFilesChanged(ev) {
    const files = Array.from(ev.target?.files || []);
    if (this.postFileInputRef?.el) this.postFileInputRef.el.value = "";
    if (!files.length) return;

    const communityId = this.state.selectedCommunity?.id;
    const channelId = this.state.selectedChannelId;
    if (!communityId || !channelId) return;

    try {
      this.state.ui.postUploading = true;
      const res = await this.api.uploadAttachments({ communityId, channelId, files });
      const items = (res.items || []).map((a) => this._normalizeAttachment(a)).filter(Boolean);
      this.state.ui.postAttachments.push(...items);
    } catch (e) {
      this.notification.add(`Upload post lỗi: ${e?.message || e}`, { type: "danger" });
    } finally {
      this.state.ui.postUploading = false;
    }
  }

  async onRemovePostAttachment(ev) {
    const aid = parseInt(ev.currentTarget?.dataset?.attachId || "0", 10);
    if (!aid) return;

    this.state.ui.postAttachments = (this.state.ui.postAttachments || []).filter((a) => a.id !== aid);
    await this._deleteDraftAttachment(aid);
  }

  // ========= SUBMIT POST =========
  async submitPost() {
    if (!this.canSubmitPost) {
      return this.notification.add("Bạn chưa nhập nội dung hoặc chưa đính kèm file.", {
        type: "warning",
      });
    }
    if (!this.state.selectedChannelId) return;

    let bodyHtml = (this.state.ui.postHtml || "").trim();
    if (!bodyHtml) bodyHtml = "<p></p>";

    if (this.state.ui.composerMode === "announcement") {
      const title = (this.state.ui.announcementTitle || "").trim();
      if (title) {
        const t = title
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;");
        bodyHtml = `<h3>${t}</h3>${bodyHtml}`;
      }
    }

    const attachmentIds = (this.state.ui.postAttachments || []).map((a) => a.id).filter(Boolean);

    await this.api.createPost({
      channelId: this.state.selectedChannelId,
      bodyHtml,
      attachmentIds,
    });

    this.state.ui.announcementTitle = "";
    this.state.ui.composerMode = "post";
    this._resetComposerAll();
    await this.refreshFeed();
  }

  // ========= COMMENTS THREAD =========
  onToggleCommentsClick(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (postId) this.toggleComments(postId);
  }

  async toggleComments(postId) {
    const cur = (this.state.openComments || {})[postId];
    if (cur?.loaded) {
      this._openCommentsRemove(postId);
      return;
    }

    this._openCommentsUpsert(postId, { loaded: false, items: [] });

    const res = await this.api.comments(postId, { limit: 50, offset: 0 });

    this._openCommentsUpsert(postId, {
      loaded: true,
      items: (res.items || [])
        .filter((x) => x && x.id)
        .map((c) => ({
          ...c,
          avatarText: this._avatarText(c.author_name),
          dateText: this._dateText(c.create_date),
          body: markup(c.body_html || ""),
          attachments: (c.attachments || [])
            .map((a) =>
              this._normalizeAttachment({ ...a, post_id: postId, comment_id: c.id })
            )
            .filter(Boolean),
        })),
    });
  }

  _findCommentEditor(postId) {
    return this.el?.querySelector(`.ch-editor--comment[data-post-id="${postId}"]`);
  }

  onCommentEditorInput(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (!postId) return;
    this.state.ui.commentHtml[postId] = ev.currentTarget?.innerHTML || "";
  }

  onCommentCmdClick(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    const cmd = ev.currentTarget?.dataset?.cmd;
    if (!postId || !cmd) return;

    const ed = this._findCommentEditor(postId);
    ed?.focus?.();

    if (cmd === "createLink") {
      const url = window.prompt("Nhập link (https://...):");
      if (url) document.execCommand("createLink", false, url);
    } else {
      document.execCommand(cmd, false, null);
    }

    if (ed) this.state.ui.commentHtml[postId] = ed.innerHTML || "";
  }

  toggleCommentEmoji(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (!postId) return;

    this._openEmojiPicker(ev, {
      kind: "comment",
      postId,
      editorEl: this._findCommentEditor(postId),
    });

    this.state.ui.commentEmojiOpen = false;
    this.state.ui.commentEmojiTarget = null;
  }

  onInsertCommentEmoji(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    const emoji = ev.currentTarget?.dataset?.emoji;
    if (!postId || !emoji) return;

    const ed = this._findCommentEditor(postId);
    ed?.focus?.();
    document.execCommand("insertText", false, emoji);

    if (ed) this.state.ui.commentHtml[postId] = ed.innerHTML || "";

    this.state.ui.commentEmojiOpen = false;
    this.state.ui.commentEmojiTarget = null;
  }

  // ========= COMMENT ATTACHMENTS =========
  onCommentAttachClick(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (!postId) return;

    this.state.ui.commentUploadTarget = postId;
    const el = this.commentFileInputRef?.el;
    if (!el) {
      this.notification.add("Không tìm thấy input comment_files (t-ref).", {
        type: "warning",
      });
      return;
    }
    el.click();
  }

  async onCommentFilesChanged(ev) {
    const files = Array.from(ev.target?.files || []);
    if (this.commentFileInputRef?.el) this.commentFileInputRef.el.value = "";

    const postId = this.state.ui.commentUploadTarget;
    if (!postId || !files.length) return;

    const communityId = this.state.selectedCommunity?.id;
    if (!communityId) return;

    try {
      this.state.ui.commentUploading = true;

      const res = await this.api.uploadAttachments({ communityId, postId, files });
      const items = (res.items || []).map((a) => this._normalizeAttachment(a)).filter(Boolean);

      const cur = this.state.ui.commentAttachments[postId] || [];
      this.state.ui.commentAttachments[postId] = [...cur, ...items];
    } catch (e) {
      this.notification.add(`Upload comment lỗi: ${e?.message || e}`, { type: "danger" });
    } finally {
      this.state.ui.commentUploading = false;
      this.state.ui.commentUploadTarget = null;
    }
  }

  async onRemoveCommentAttachment(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    const aid = parseInt(ev.currentTarget?.dataset?.attachId || "0", 10);
    if (!postId || !aid) return;

    const cur = this.state.ui.commentAttachments[postId] || [];
    this.state.ui.commentAttachments[postId] = cur.filter((x) => x.id !== aid);

    await this._deleteDraftAttachment(aid);
  }

  onSubmitCommentClick(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (postId) this.submitComment(postId);
  }

  async submitComment(postId) {
    const htmlDraft = (this.state.ui.commentHtml?.[postId] || "").trim();
    const atts = this.state.ui.commentAttachments?.[postId] || [];
    const attachmentIds = atts.map((a) => a.id).filter(Boolean);

    let bodyHtml = htmlDraft;
    if (!bodyHtml && attachmentIds.length) bodyHtml = "<p></p>";

    const plain = this._stripHtml(bodyHtml).replace(/\s+/g, "").trim();
    if (!plain && !attachmentIds.length) return;

    try {
      await this.api.createComment({ postId, bodyHtml, attachmentIds });
    } catch (e) {
      this.notification.add(`Gửi bình luận lỗi: ${e?.message || e}`, { type: "danger" });
      return;
    }

    this.state.ui.commentHtml[postId] = "";
    this.state.ui.commentAttachments[postId] = [];

    const ed = this._findCommentEditor(postId);
    if (ed) ed.innerHTML = "";

    this._openCommentsRemove(postId);
    await this.toggleComments(postId);

    await this.refreshFeed();
  }

  // ========= REACTIONS =========
  async onReactClick(ev) {
    const btn = ev.currentTarget;
    const emoji = btn.dataset.emoji;
    const postId = Number(btn.dataset.postId);

    const postIdx = (this.state.feed || []).findIndex((p) => p.id === postId);
    if (postIdx < 0) return;

    const post = this.state.feed[postIdx];

    const res = await this.api.toggleReaction({
      communityId: post.community_id,
      postId,
      emoji,
    });

    if (res?.reactions) {
      const newPost = { ...post, reactions: [...res.reactions] };
      const newFeed = [...this.state.feed];
      newFeed[postIdx] = newPost;
      this.state.feed = newFeed;
    }
  }

  // ========= EDIT / DELETE =========
  _getPostById(postId) {
    return (this.state.feed || []).find((p) => p.id === postId) || null;
  }

  _getCommentById(postId, commentId) {
    const th = (this.state.openComments || {})[postId];
    if (!th?.loaded) return null;
    return (th.items || []).find((c) => c.id === commentId) || null;
  }

  async _callApiOrRpc(fnName, fnArgs, fallbackRoute = null, fallbackParams = null) {
    const fn = this.api?.[fnName];
    if (typeof fn === "function") {
      return await fn.call(this.api, ...(fnArgs || []));
    }
    if (fallbackRoute) {
      return await this.rpc(fallbackRoute, fallbackParams || {});
    }
    throw new Error(`Missing API function: ${fnName}`);
  }

  openEditPost(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (!postId) return;

    const p = this._getPostById(postId);
    if (!p) return;

    if (!this._canEditPost(p)) {
      this.notification.add("Bạn không có quyền sửa bài viết này.", { type: "warning" });
      return;
    }

    this.state.ui.editPostId = postId;
    setTimeout(() => {
      const el = this.editPostEditorRef?.el;
      if (el) el.innerHTML = p.body_html || "";
    }, 0);
  }

  closeEditPost() {
    this.state.ui.editPostId = null;
    const el = this.editPostEditorRef?.el;
    if (el) el.innerHTML = "";
  }

  async saveEditPost() {
    const postId = this.state.ui.editPostId;
    if (!postId) return;

    const p = this._getPostById(postId);
    if (!p) return;

    if (!this._canEditPost(p)) {
      this.notification.add("Bạn không có quyền sửa bài viết này.", { type: "warning" });
      return;
    }

    const el = this.editPostEditorRef?.el;
    const bodyHtml = (el?.innerHTML || "").trim();

    try {
      await this._callApiOrRpc(
        "updatePost",
        [{ postId, bodyHtml }],
        "/community_hub/post/update",
        { post_id: postId, body_html: bodyHtml }
      );

      p.body_html = bodyHtml;
      p.body = markup(bodyHtml);

      this.notification.add("Đã lưu bài viết ✅", { type: "success" });
      this.closeEditPost();
      await this.refreshFeed();
    } catch (e) {
      this.notification.add(`Lưu bài viết lỗi: ${e?.message || e}`, { type: "danger" });
    }
  }

  async deletePost(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (!postId) return;

    const p = this._getPostById(postId);
    if (!p) return;

    if (!this._canEditPost(p)) {
      this.notification.add("Bạn không có quyền xoá bài viết này.", { type: "warning" });
      return;
    }

    const ok = window.confirm("Xoá bài viết này?");
    if (!ok) return;

    try {
      await this._callApiOrRpc(
        "deletePost",
        [{ postId }],
        "/community_hub/post/delete",
        { post_id: postId }
      );

      this.state.feed = (this.state.feed || []).filter((x) => x.id !== postId);
      this._openCommentsRemove(postId);

      this.notification.add("Đã xoá bài viết 🗑️", { type: "warning" });
      await this.refreshFeed();
    } catch (e) {
      this.notification.add(`Xoá bài viết lỗi: ${e?.message || e}`, { type: "danger" });
    }
  }

  openEditComment(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    const commentId = parseInt(ev.currentTarget?.dataset?.commentId || "0", 10);
    if (!postId || !commentId) return;

    const c = this._getCommentById(postId, commentId);
    if (!c) {
      this.notification.add("Không tìm thấy comment (bạn cần mở thread trước).", {
        type: "warning",
      });
      return;
    }

    if (!this._canEditComment(c)) {
      this.notification.add("Bạn không có quyền sửa bình luận này.", { type: "warning" });
      return;
    }

    this.state.ui.editCommentId = commentId;
    this.state.ui.editCommentPostId = postId;

    setTimeout(() => {
      const el = this.editCommentEditorRef?.el;
      if (el) el.innerHTML = c.body_html || "";
    }, 0);
  }

  closeEditComment() {
    this.state.ui.editCommentId = null;
    this.state.ui.editCommentPostId = null;
    const el = this.editCommentEditorRef?.el;
    if (el) el.innerHTML = "";
  }

  async saveEditComment() {
    const commentId = this.state.ui.editCommentId;
    const postId = this.state.ui.editCommentPostId;
    if (!commentId || !postId) return;

    const c = this._getCommentById(postId, commentId);
    if (!c) return;

    if (!this._canEditComment(c)) {
      this.notification.add("Bạn không có quyền sửa bình luận này.", { type: "warning" });
      return;
    }

    const el = this.editCommentEditorRef?.el;
    const bodyHtml = (el?.innerHTML || "").trim();

    try {
      await this._callApiOrRpc(
        "updateComment",
        [{ commentId, bodyHtml }],
        "/community_hub/comment/update",
        { comment_id: commentId, body_html: bodyHtml }
      );

      c.body_html = bodyHtml;
      c.body = markup(bodyHtml);

      this.notification.add("Đã lưu bình luận ✅", { type: "success" });
      this.closeEditComment();

      this._openCommentsRemove(postId);
      await this.toggleComments(postId);
      await this.refreshFeed();
    } catch (e) {
      this.notification.add(`Lưu bình luận lỗi: ${e?.message || e}`, { type: "danger" });
    }
  }

  async deleteComment(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    const commentId = parseInt(ev.currentTarget?.dataset?.commentId || "0", 10);
    if (!postId || !commentId) return;

    const c = this._getCommentById(postId, commentId);
    if (!c) return;

    if (!this._canEditComment(c)) {
      this.notification.add("Bạn không có quyền xoá bình luận này.", { type: "warning" });
      return;
    }

    const ok = window.confirm("Xoá bình luận này?");
    if (!ok) return;

    try {
      await this._callApiOrRpc(
        "deleteComment",
        [{ commentId }],
        "/community_hub/comment/delete",
        { comment_id: commentId }
      );

      const th = (this.state.openComments || {})[postId];
      if (th?.loaded) {
        th.items = (th.items || []).filter((x) => x.id !== commentId);
        this._openCommentsUpsert(postId, { ...th });
      }

      this.notification.add("Đã xoá bình luận 🗑️", { type: "warning" });
      await this.refreshFeed();
    } catch (e) {
      this.notification.add(`Xoá bình luận lỗi: ${e?.message || e}`, { type: "danger" });
    }
  }

  // ========= CREATE COMMUNITY / CHANNEL =========
  toggleNewCommunity() {
    this.state.ui.showNewCommunity = !this.state.ui.showNewCommunity;
    if (!this.state.ui.showNewCommunity) {
      this.state.ui.newCommunityName = "";
      this.state.ui.newCommunityPublic = false;
      this.state.ui.newCommunityPolicy = "invite";
    }
  }

  onNewCommunityKeydown(ev) {
    if (ev.key === "Enter") {
      ev.preventDefault();
      this.submitNewCommunity();
    }
    if (ev.key === "Escape") {
      ev.preventDefault();
      this.toggleNewCommunity();
    }
  }

  async submitNewCommunity() {
    const name = (this.state.ui.newCommunityName || "").trim();
    if (!name) {
      return this.notification.add("Vui lòng nhập tên Community", { type: "warning" });
    }

    await this.api.createCommunity({
      name,
      joinPolicy: this.state.ui.newCommunityPolicy,
      isPublic: this.state.ui.newCommunityPublic,
      descriptionHtml: null,
    });

    this.toggleNewCommunity();
    await this.loadBootstrap();
  }

  toggleNewChannel() {
    if (!this.canManage) return;
    this.state.ui.showNewChannel = !this.state.ui.showNewChannel;
    if (!this.state.ui.showNewChannel) this.state.ui.newChannelName = "";
  }

  onNewChannelKeydown(ev) {
    if (ev.key === "Enter") {
      ev.preventDefault();
      this.submitNewChannel();
    }
    if (ev.key === "Escape") {
      ev.preventDefault();
      this.toggleNewChannel();
    }
  }

  async submitNewChannel() {
    if (!this.canManage) return;

    const name = (this.state.ui.newChannelName || "").trim();
    if (!name) {
      return this.notification.add("Vui lòng nhập tên Channel", { type: "warning" });
    }

    const communityId = this.state.selectedCommunity?.id;
    if (!communityId) {
      return this.notification.add("Bạn chưa chọn Community", { type: "warning" });
    }

    await this.api.createChannel({ communityId, name, sequence: 10 });

    this.state.ui.newChannelName = "";
    this.state.ui.showNewChannel = false;

    await this.reloadChannels();
    const created = this.state.channels.slice().sort((a, b) => b.id - a.id)[0];
    if (created?.id) {
      this.state.selectedChannelId = created.id;
      await this.refreshFeed();
    }
  }

  // ========= JOIN =========
  async joinCommunity(ev) {
    const cid = parseInt(ev.currentTarget?.dataset?.communityId || "0", 10);
    if (!cid) return;

    await this.api.joinCommunity(cid);
    this.notification.add("Đã tham gia community ✅", { type: "success" });
    await this.loadBootstrap();
  }

  // ========= SETTINGS / MEMBERS =========
  async toggleSettings() {
    if (!this.state.selectedCommunity) return;
    this.state.ui.settingsOpen = !this.state.ui.settingsOpen;
    if (this.state.ui.settingsOpen) await this.loadManageData();
  }

  onSettingsTabClick(ev) {
    const tab = ev.currentTarget?.dataset?.tab;
    if (tab) this.state.ui.settingsTab = tab;
  }

  async loadManageData() {
    const c = this.state.selectedCommunity;
    if (!c?.id) return;

    const res = await this.api.members(c.id);
    this.state.ui.members = res.items || [];

    const me = this.state.ui.members.find((m) => m.user_id === this.state.user?.id);
    this.state.ui.myRole = me?.role || c.my_role || null;

    this.state.ui.communityForm = {
      name: c.name || "",
      join_policy: c.join_policy || "invite",
      is_public: !!c.is_public,
      description_html: c.description_html || "",
    };

    const ch = this.selectedChannel;
    this.state.ui.channelForm = { name: ch?.name || "", sequence: ch?.sequence ?? 10 };

    this.state.ui.memberQuery = "";
    this.state.ui.memberResults = [];
  }

  async onMemberSearchInput(ev) {
    this.state.ui.memberQuery = ev.target.value;
    const q = (this.state.ui.memberQuery || "").trim();
    if (!q || !this.canManage) {
      this.state.ui.memberResults = [];
      return;
    }
    const res = await this.api.searchUsers({
      communityId: this.state.selectedCommunity.id,
      q,
      limit: 10,
    });
    this.state.ui.memberResults = res.items || [];
  }

  onInviteClick(ev) {
    const uid = parseInt(ev.currentTarget?.dataset?.userId || "0", 10);
    if (!uid) return;
    const u = this.state.ui.memberResults.find((x) => x.id === uid);
    if (u) this.inviteUser(u);
  }

  async inviteUser(u) {
    if (!this.canManage) return;
    await this.api.invite({ communityId: this.state.selectedCommunity.id, userIds: [u.id] });
    await this.loadManageData();
  }

  onKickClick(ev) {
    const uid = parseInt(ev.currentTarget?.dataset?.userId || "0", 10);
    if (!uid) return;
    const m = this.state.ui.members.find((x) => x.user_id === uid);
    if (m) this.kickMember(m);
  }

  async kickMember(m) {
    if (!this.canManage) return;
    await this.api.kick({ communityId: this.state.selectedCommunity.id, userId: m.user_id });
    await this.loadManageData();
  }

  onRoleChange(ev) {
    const uid = parseInt(ev.currentTarget?.dataset?.userId || "0", 10);
    const role = ev.target.value;
    if (!uid || !role) return;
    const m = this.state.ui.members.find((x) => x.user_id === uid);
    if (m) this.changeRole(m, role);
  }

  async changeRole(m, role) {
    if (!this.canManage) return;
    await this.api.setRole({ communityId: this.state.selectedCommunity.id, userId: m.user_id, role });
    await this.loadManageData();
  }

  async saveCommunitySettings() {
    if (!this.canManage) return;
    await this.api.updateCommunity({
      communityId: this.state.selectedCommunity.id,
      vals: { ...this.state.ui.communityForm },
    });
    await this.loadBootstrap();
    this.state.ui.settingsOpen = true;
    await this.loadManageData();
  }

  async saveChannelSettings() {
    if (!this.canManage || !this.state.selectedChannelId) return;
    await this.api.updateChannel({
      channelId: this.state.selectedChannelId,
      vals: { ...this.state.ui.channelForm },
    });
    await this.reloadChannels();
    await this.loadManageData();
  }

  async deleteSelectedChannel() {
    if (!this.canManage || !this.state.selectedChannelId) return;
    await this.api.deleteChannel({ channelId: this.state.selectedChannelId });
    await this.reloadChannels();
    this.state.selectedChannelId = this.state.channels[0]?.id || null;
    await this.refreshFeed();
    await this.loadManageData();
  }

  // ========= OPEN ATTACHMENT =========
  onOpenAttachmentClick(ev) {
    const url = ev.currentTarget?.dataset?.url;
    if (!url) return;
    window.open(url, "_blank", "noopener,noreferrer");
  }

  async _deleteDraftAttachment(attachmentId) {
    const aid = parseInt(attachmentId || "0", 10);
    if (!aid) return;
    try {
      await this.api.deleteAttachment(aid);
    } catch (e) {
      this.notification.add(`Không xoá được file trên server (#${aid}).`, {
        type: "warning",
      });
    }
  }

  // ========= PASTE IMAGE =========
  _extractClipboardFiles(ev) {
    const dt = ev.clipboardData;
    const out = [];

    const items = Array.from(dt?.items || []);
    for (const it of items) {
      if (it.kind === "file") {
        const f = it.getAsFile();
        if (f) out.push(f);
      }
    }

    const files = Array.from(dt?.files || []);
    out.push(...files);

    const seen = new Set();
    const uniq = [];
    for (const f of out) {
      const k = `${f.name}|${f.size}|${f.type}`;
      if (!seen.has(k)) {
        seen.add(k);
        uniq.push(f);
      }
    }
    return uniq;
  }

  _filterImageFiles(files) {
    return (files || []).filter((f) => (f?.type || "").toLowerCase().startsWith("image/"));
  }

  async onPostPaste(ev) {
    const files = this._filterImageFiles(this._extractClipboardFiles(ev));
    if (!files.length) return;

    ev.preventDefault();

    const communityId = this.state.selectedCommunity?.id;
    const channelId = this.state.selectedChannelId;
    if (!communityId || !channelId) return;

    try {
      this.state.ui.postUploading = true;

      const res = await this.api.uploadAttachments({ communityId, channelId, files });
      const items = (res.items || []).map((a) => this._normalizeAttachment(a)).filter(Boolean);

      this.state.ui.postAttachments.push(...items);
      this.notification.add(`Đã đính kèm ${items.length} ảnh từ clipboard ✅`, { type: "success" });
    } catch (e) {
      this.notification.add(`Paste upload lỗi: ${e?.message || e}`, { type: "danger" });
    } finally {
      this.state.ui.postUploading = false;
    }
  }

  async onCommentPaste(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (!postId) return;

    const files = this._filterImageFiles(this._extractClipboardFiles(ev));
    if (!files.length) return;

    ev.preventDefault();

    const communityId = this.state.selectedCommunity?.id;
    if (!communityId) return;

    try {
      this.state.ui.commentUploading = true;

      const res = await this.api.uploadAttachments({ communityId, postId, files });
      const items = (res.items || []).map((a) => this._normalizeAttachment(a)).filter(Boolean);

      const cur = this.state.ui.commentAttachments[postId] || [];
      this.state.ui.commentAttachments[postId] = [...cur, ...items];

      this.notification.add(`Đã đính kèm ${items.length} ảnh ✅`, { type: "success" });
    } catch (e) {
      this.notification.add(`Paste upload lỗi: ${e?.message || e}`, { type: "danger" });
    } finally {
      this.state.ui.commentUploading = false;
    }
  }

  // ========= SEARCH (SIDEBAR) =========
  get communityQuery() {
    return (this.state.ui.communityQuery || "").trim();
  }
  get hasCommunitySearch() {
    return this.communityQuery.length > 0;
  }
  get channelQuery() {
    return (this.state.ui.channelQuery || "").trim();
  }
  get hasChannelSearch() {
    return this.channelQuery.length > 0;
  }

  clearCommunitySearch() {
    this.state.ui.communityQuery = "";
  }
  clearChannelSearch() {
    this.state.ui.channelQuery = "";
  }

  get filteredCommunities() {
    const list = this.state.communities || [];
    const q = this.communityQuery;
    if (!q) return list;
    return list.filter((c) => this._match(q, `${c?.name || ""} ${c?.my_state || ""}`));
  }

  get filteredChannels() {
    const list = this.state.channels || [];
    const q = this.channelQuery;
    if (!q) return list;
    return list.filter((ch) => this._match(q, `${ch?.name || ""}`));
  }

  // ========= POST FORMAT (font/size/color) =========
  onPostSelChange() {
    this._postSelRange = this._captureRange(this.postEditorRef?.el);
  }
  capturePostRange() {
    this._postSelRange = this._captureRange(this.postEditorRef?.el);
  }

  onPostBlockChange(ev) {
    const tag = (ev?.target?.value || "P").trim();
    const ed = this.postEditorRef?.el;
    if (!ed) return;

    ed.focus?.();
    if (this._postSelRange) this._restoreRange(this._postSelRange);

    try {
      document.execCommand("formatBlock", false, tag);
    } catch (e) {}

    this.state.ui.postHtml = ed.innerHTML || "";
    this._postSelRange = this._captureRange(ed);
  }

  _escapeHtml(s) {
    return String(s || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  _insertHtmlAtCaret(editorEl, html) {
    if (!editorEl || !html) return;
    editorEl.focus?.();

    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return;

    const range = sel.getRangeAt(0);
    range.deleteContents();

    const wrap = document.createElement("div");
    wrap.innerHTML = html;

    const frag = document.createDocumentFragment();
    let node;
    let lastNode = null;
    while ((node = wrap.firstChild)) {
      lastNode = frag.appendChild(node);
    }

    range.insertNode(frag);

    if (lastNode) {
      const nr = document.createRange();
      nr.setStartAfter(lastNode);
      nr.collapse(true);
      sel.removeAllRanges();
      sel.addRange(nr);
    }
  }

  _applyPostInlineStyle(style) {
    const ed = this.postEditorRef?.el;
    if (!ed) return;

    ed.focus?.();
    if (this._postSelRange) this._restoreRange(this._postSelRange);

    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return;
    const range = sel.getRangeAt(0);

    const span = document.createElement("span");
    if (style.fontFamily) span.style.fontFamily = style.fontFamily;
    if (style.fontSizePx) span.style.fontSize = `${style.fontSizePx}px`;
    if (style.color) span.style.color = style.color;
    if (style.backgroundColor) span.style.backgroundColor = style.backgroundColor;

    if (range.collapsed) {
      const zwsp = document.createTextNode("\u200B");
      span.appendChild(zwsp);
      range.insertNode(span);

      const nr = document.createRange();
      nr.setStart(zwsp, 1);
      nr.setEnd(zwsp, 1);
      sel.removeAllRanges();
      sel.addRange(nr);
    } else {
      const frag = range.extractContents();
      span.appendChild(frag);
      range.insertNode(span);

      range.setStartAfter(span);
      range.setEndAfter(span);
      sel.removeAllRanges();
      sel.addRange(range);
    }

    this.state.ui.postHtml = ed.innerHTML || "";
    this._postSelRange = this._captureRange(ed);
  }

  onPostColorChange(ev) {
    const c = ev?.target?.value || "#111111";
    this.state.ui.postTextColor = c;
    this._applyPostInlineStyle({ color: c });
  }

  onPostHighlightChange(ev) {
    const c = ev?.target?.value || "#fff3a0";
    this.state.ui.postBgColor = c;
    this._applyPostInlineStyle({ backgroundColor: c });
  }

  onPostSizeChange(ev) {
    const px = Number(ev?.target?.value || 0);
    if (!px) return;
    this._applyPostInlineStyle({ fontSizePx: px });
  }

  insertPostChecklist() {
    const ed = this.postEditorRef?.el;
    if (!ed) return;

    ed.focus?.();
    if (this._postSelRange) this._restoreRange(this._postSelRange);

    const sel = window.getSelection();
    const text = (sel?.toString?.() || "").trim();
    const lines = text
      ? text.split(/\n+/).map((x) => x.trim()).filter(Boolean)
      : [""];

    const itemsHtml = lines
      .map(
        (l) =>
          `<li><input type="checkbox" disabled="disabled"/> <span>${this._escapeHtml(l)}</span></li>`
      )
      .join("");

    const html = `<ul class="ch-checklist">${itemsHtml}</ul><p></p>`;
    this._insertHtmlAtCaret(ed, html);

    this.state.ui.postHtml = ed.innerHTML || "";
    this._postSelRange = this._captureRange(ed);
  }
}

registry.category("actions").add("community_hub.client_action", CommunityHubClientAction);
