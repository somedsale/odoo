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

console.log("[community_hub] app.js loaded ✅");

export class CommunityHubClientAction extends Component {
  static template = "community_hub.ClientAction";

  setup() {
    // services
    this.bus = this.env.services.bus_service;
    this.notification = this.env.services.notification;
    this.rpc = this.env.services.rpc;

    // api
    this.api = makeCommunityAPI(this.rpc);

    // refs
    this.postEditorRef = useRef("post_editor");
    this.postFileInputRef = useRef("post_files");
    this.commentFileInputRef = useRef("comment_files");
this.editPostEditorRef = useRef("edit_post_editor");
this.editCommentEditorRef = useRef("edit_comment_editor");

    // internal bus tracking
    this._busStarted = false;
    this._busCommunityId = null;

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

      openComments: {}, // {postId:{loaded,items}}

      ui: {
        activeTab: "posts",
        badges: {},

        composerMode: "post",
        announcementTitle: "",
        postHtml: "",
        postAttachments: [],
        postUploading: false,
        postEmojiOpen: false,

        commentDraft: {},
        commentHtml: {},
        commentAttachments: {}, // {postId:[att,...]}
        commentUploadTarget: null,
        commentUploading: false,
        commentEmojiOpen: false,
        commentEmojiTarget: null,
editPostId: null,
editCommentId: null,

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

        communityForm: { name: "", join_policy: "invite", is_public: false, description_html: "" },
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
        const payload = Array.isArray(n) ? n[1] : (n?.payload ?? n?.message ?? n);
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
          this._bumpBadge(payload.community_id);
          if (payload.actor_id && payload.actor_id !== this.state.user?.id) {
            this.notification.add(
              `${payload.actor_name || "Ai đó"} đăng bài mới trong ${payload.community_name || "community"}`,
              { type: "info" }
            );
          }
          continue;
        }

        if (payload.type === "notify_comment") {
          this._bumpBadge(payload.community_id);
          if (payload.actor_id && payload.actor_id !== this.state.user?.id) {
            this.notification.add(
              `${payload.actor_name || "Ai đó"} bình luận mới trong ${payload.community_name || "community"}`,
              { type: "info" }
            );
          }
          continue;
        }

        // realtime update when you're inside same community
        const curCid = this.state.selectedCommunity?.id;
        if (curCid && payload.community_id === curCid) {
          if (["channel_created", "channel_updated", "channel_deleted"].includes(payload.type)) {
            this.reloadChannels();
          }
          if (["post_created", "comment_created", "reaction_toggled"].includes(payload.type)) {
            this.refreshFeed();
          }
          if (payload.type === "members_changed" && this.state.ui.settingsOpen) {
            this.loadManageData();
          }
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

      // ✅ add channel trước
      this._syncBusChannels();

      // ✅ rồi mới start
      this.bus.start();
    } else {
      this._syncBusChannels();
    }
  });


    onWillUnmount(() => {
      if (this._busStarted) {
        this.bus.removeEventListener("notification", this._onBusNotification);
      }
    });

    useEffect(
      () => this._syncBusChannels(),
      () => [this.state.user?.id, this.state.selectedCommunity?.id]
    );
  }

  // ========= GETTERS =========
  get isJoined() {
    return this.state.selectedCommunity?.my_state === "joined";
  }

  get canManage() {
    return ["owner", "admin"].includes(this.state.ui.myRole);
  }

  get selectedChannel() {
    return this.state.channels.find((c) => c.id === this.state.selectedChannelId) || null;
  }

  get emojis() {
    return ["😀","😅","😂","😍","👍","👏","🙏","🔥","🎉","✅","❗","💡","📌","❤️","😡","😢"];
  }

  get canSubmitPost() {
    const html = (this.state.ui.postHtml || "").trim();
    const hasText = this._stripHtml(html).trim().length > 0;
    const hasAtt = (this.state.ui.postAttachments || []).length > 0;
    return hasText || hasAtt;
  }

  get flattenFiles() {
    const out = [];
    for (const p of this.state.feed || []) {
      for (const a of p.attachments || []) {
        out.push({
          key: `p${p.id}-a${a.id}`,
          name: a.name,
          url: a.download_url || a.open_url || a.url,
          from: `${p.author_name || ""}`,
        });
      }
    }
    return out;
  }

  get flattenPhotos() {
    const out = [];
    for (const p of this.state.feed || []) {
      for (const a of p.attachments || []) {
        if ((a.mimetype || "").startsWith("image/")) {
          out.push({
            key: `p${p.id}-a${a.id}`,
            url: a.open_url || a.url,
          });
        }
      }
    }
    return out;
  }

  // ========= UTIL =========
  _stripHtml(html) {
    const div = document.createElement("div");
    div.innerHTML = html || "";
    return div.textContent || div.innerText || "";
  }

  _escapeTextToHtml(text) {
    const safe = (text || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll("\n", "<br/>");
    return `<p>${safe}</p>`;
  }

  _avatarText(name) {
    const s = (name || "").trim();
    if (!s) return "?";
    const parts = s.split(/\s+/).slice(0, 2);
    return parts.map((p) => (p[0] || "").toUpperCase()).join("");
  }

  _dateText(dt) {
    if (!dt) return "";
    const s = String(dt);
    return s.replace("T", " ").slice(0, 16);
  }

  _bumpBadge(cid) {
    if (!cid) return;
    this.state.ui.badges[cid] = (this.state.ui.badges[cid] || 0) + 1;
  }

  _clearBadge(cid) {
    if (!cid) return;
    delete this.state.ui.badges[cid];
  }

  // ========= BUS CHANNELS =========
  _syncBusChannels() {
    if (!this._busStarted) return;

    if (this.state.user?.id) {
      try {
        this.bus.addChannel("community_hub.user", this.state.user.id);
      } catch (e) {}
    }

    const newCid = this.state.selectedCommunity?.id || null;
    if (this._busCommunityId && this._busCommunityId !== newCid) {
      try {
        this.bus.deleteChannel("community_hub", this._busCommunityId);
      } catch (e) {}
    }
    if (newCid) {
      try {
        this.bus.addChannel("community_hub", newCid);
      } catch (e) {}
    }
    this._busCommunityId = newCid;
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
    if (mt.includes("spreadsheet") || ["xls","xlsx","ods","csv"].includes(ext)) return "sheet";
    if (mt.includes("word") || ["doc","docx","odt"].includes(ext)) return "doc";
    if (mt.includes("presentation") || ["ppt","pptx","odp"].includes(ext)) return "slide";
    if (mt.startsWith("video/")) return "video";
    if (mt.startsWith("audio/")) return "audio";
    if (["zip","rar","7z","tar","gz"].includes(ext)) return "archive";
    return "file";
  }

  _iconText(kind) {
    switch (kind) {
      case "image": return "🖼";
      case "pdf": return "PDF";
      case "sheet": return "XLS";
      case "doc": return "DOC";
      case "slide": return "PPT";
      case "video": return "VID";
      case "audio": return "AUD";
      case "archive": return "ZIP";
      default: return "FILE";
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
      a.download_url ||
      (a.id ? `/web/content/${a.id}?download=true` : openUrl);

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
// ===== Reactive helpers (avoid delete-mutation that may not rerender) =====
_setBadges(next) {
  this.state.ui.badges = next || {};
}

_bumpBadge(cid) {
  if (!cid) return;
  const cur = this.state.ui.badges || {};
  this._setBadges({ ...cur, [cid]: (cur[cid] || 0) + 1 });
}

_clearBadge(cid) {
  if (!cid) return;
  const cur = this.state.ui.badges || {};
  if (!(cid in cur)) return;
  const next = { ...cur };
  delete next[cid];
  this._setBadges(next);
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
_canEditPost(p) {
  const myId = this.state.user?.id;
  if (!myId) return false;
  return p.create_uid === myId;
}

_canEditComment(c) {
  const myId = this.state.user?.id;
  if (!myId) return false;
  return c.create_uid === myId;
}

openEditPost(ev) {
  const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
  if (!postId) return;
  const p = this.state.feed.find((x) => x.id === postId);
  if (!p) return;
  if (!this._canEditPost(p)) return;

  this.state.ui.editPostId = postId;

  // set HTML vào editor sau khi modal render 1 nhịp
  setTimeout(() => {
    if (this.editPostEditorRef?.el) {
      this.editPostEditorRef.el.innerHTML = p.body_html || "";
      this.editPostEditorRef.el.focus();
    }
  }, 0);
}

closeEditPost() {
  this.state.ui.editPostId = null;
  if (this.editPostEditorRef?.el) this.editPostEditorRef.el.innerHTML = "";
}

async saveEditPost() {
  const postId = this.state.ui.editPostId;
  if (!postId) return;

  const html = (this.editPostEditorRef?.el?.innerHTML || "").trim();
  try {
    await this.api.updatePost({ postId, bodyHtml: html });
    this.closeEditPost();
    await this.refreshFeed();
    this.notification.add("Đã cập nhật bài viết ✅", { type: "success" });
  } catch (e) {
    this.notification.add(`Sửa bài viết lỗi: ${e?.message || e}`, { type: "danger" });
  }
}

async deletePost(ev) {
  const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
  if (!postId) return;

  const p = this.state.feed.find((x) => x.id === postId);
  if (!p || !this._canEditPost(p)) return;

  if (!window.confirm("Xoá bài viết này? (kèm bình luận)")) return;

  try {
    await this.api.deletePost({ postId });
    await this.refreshFeed();
    this.notification.add("Đã xoá bài viết ✅", { type: "success" });
  } catch (e) {
    this.notification.add(`Xoá bài viết lỗi: ${e?.message || e}`, { type: "danger" });
  }
}


// ===== COMMENT =====
openEditComment(ev) {
  const commentId = parseInt(ev.currentTarget?.dataset?.commentId || "0", 10);
  if (!commentId) return;

  // tìm comment trong openComments
  let found = null;
  for (const k of Object.keys(this.state.openComments || {})) {
    const it = this.state.openComments[k]?.items || [];
    const c = it.find((x) => x.id === commentId);
    if (c) { found = c; break; }
  }
  if (!found || !this._canEditComment(found)) return;

  this.state.ui.editCommentId = commentId;

  setTimeout(() => {
    if (this.editCommentEditorRef?.el) {
      this.editCommentEditorRef.el.innerHTML = found.body_html || "";
      this.editCommentEditorRef.el.focus();
    }
  }, 0);
}

closeEditComment() {
  this.state.ui.editCommentId = null;
  if (this.editCommentEditorRef?.el) this.editCommentEditorRef.el.innerHTML = "";
}

async saveEditComment() {
  const commentId = this.state.ui.editCommentId;
  if (!commentId) return;

  const html = (this.editCommentEditorRef?.el?.innerHTML || "").trim();
  try {
    await this.api.updateComment({ commentId, bodyHtml: html });
    this.closeEditComment();

    // reload thread: easiest là refreshFeed + reopen thread đang mở
    await this.refreshFeed();
    // optional: bạn có thể tự reload comments theo postId, nhưng refreshFeed là đủ nhanh
    this.notification.add("Đã cập nhật bình luận ✅", { type: "success" });
  } catch (e) {
    this.notification.add(`Sửa bình luận lỗi: ${e?.message || e}`, { type: "danger" });
  }
}

async deleteComment(ev) {
  const commentId = parseInt(ev.currentTarget?.dataset?.commentId || "0", 10);
  if (!commentId) return;

  // tìm comment như trên
  let found = null;
  let postId = null;
  for (const k of Object.keys(this.state.openComments || {})) {
    const it = this.state.openComments[k]?.items || [];
    const c = it.find((x) => x.id === commentId);
    if (c) { found = c; postId = parseInt(k, 10); break; }
  }
  if (!found || !this._canEditComment(found)) return;

  if (!window.confirm("Xoá bình luận này?")) return;

  try {
    await this.api.deleteComment({ commentId });
    // reload thread tại postId
    if (postId) {
      delete this.state.openComments[postId];
      await this.toggleComments(postId);
    } else {
      await this.refreshFeed();
    }
    this.notification.add("Đã xoá bình luận ✅", { type: "success" });
  } catch (e) {
    this.notification.add(`Xoá bình luận lỗi: ${e?.message || e}`, { type: "danger" });
  }
}

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
      this.notification.add(`Không xoá được file trên server (#${aid}).`, { type: "warning" });
    }
  }

  // ========= BOOTSTRAP =========
  async loadBootstrap() {
    try {
      this.state.loading = true;

      const data = await this.api.bootstrap();
      this.state.user = data.user || null;

      this.state.communities = data.communities || [];
      this.state.selectedCommunity = data.selected || null;

      // not joined => no channels/feed
      if (this.state.selectedCommunity && this.state.selectedCommunity.my_state !== "joined") {
        this.state.channels = [];
        this.state.selectedChannelId = null;
        this.state.feed = [];
        this.state.feedOffset = 0;
        this.state.feedHasMore = false;
        this.state.openComments = {};
        this.state.ui.myRole = this.state.selectedCommunity?.my_role || null;

        this._resetComposerAll();
        this.state.loading = false;
        return;
      }

      if (!this.state.selectedCommunity || !this.state.communities.length) {
        this.state.channels = [];
        this.state.selectedChannelId = null;
        this.state.feed = [];
        this.state.feedOffset = 0;
        this.state.feedHasMore = false;
        this.state.openComments = {};
        this._resetComposerAll();
        this.state.loading = false;
        return;
      }

      this.state.channels = data.channels || [];
      this.state.selectedChannelId = this.state.channels[0]?.id || null;

      this.state.feed = [];
      this.state.feedOffset = 0;
      this.state.feedHasMore = false;
      this.state.openComments = {};
      this.state.ui.settingsOpen = false;
      this.state.ui.myRole = this.state.selectedCommunity?.my_role || null;

      this._resetComposerAll();
      this.state.loading = false;

      if (this.state.selectedChannelId) {
        await this.refreshFeed();
      }
    } catch (e) {
      this.state.loading = false;
      this.notification.add(`Bootstrap error: ${e?.message || e}`, { type: "danger" });
    }
  }

  _resetComposerAll() {
    // post
    this.state.ui.postHtml = "";
    this.state.ui.postAttachments = [];
    this.state.ui.postUploading = false;
    this.state.ui.postEmojiOpen = false;
    if (this.postEditorRef?.el) this.postEditorRef.el.innerHTML = "";

    // comment
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
    this._clearBadge(c.id);
    this.state.ui.settingsOpen = false;
    this.state.ui.myRole = c.my_role || null;

    if (c.my_state !== "joined") {
      this.state.channels = [];
      this.state.selectedChannelId = null;
      this.state.feed = [];
      this.state.feedOffset = 0;
      this.state.feedHasMore = false;
      this.state.openComments = {};
      this._resetComposerAll();
      return;
    }

    await this.reloadChannels();

    this.state.selectedChannelId = this.state.channels[0]?.id || null;
    this.state.feed = [];
    this.state.feedOffset = 0;
    this.state.feedHasMore = false;
    this.state.openComments = {};
    this._resetComposerAll();

    if (this.state.selectedChannelId) {
      await this.refreshFeed();
    }
  }

  async selectChannel(ev) {
    const id = parseInt(ev.currentTarget?.dataset?.channelId || "0", 10);
    if (!id) return;

    this.state.selectedChannelId = id;
    this.state.feed = [];
    this.state.feedOffset = 0;
    this.state.feedHasMore = false;
    this.state.openComments = {};
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

      this._clearBadge(comm?.id);

      const items = (res.items || []).map((p) => ({
        ...p,
        is_owner: comm?.owner_id && p.author_id === comm.owner_id,
        avatarText: this._avatarText(p.author_name),
        dateText: this._dateText(p.create_date),
        body: markup(p.body_html || ""),
        attachments: (p.attachments || []).map((a) => this._normalizeAttachment(a)).filter(Boolean),
        reactions: p.reactions || [],
      }));

      this.state.feed = items;
      this.state.feedOffset = items.length;
      this.state.feedHasMore = !!res.has_more;
    } catch (e) {
      this.notification.add("Không thể tải feed (có thể bạn không còn quyền).", { type: "warning" });
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
      attachments: (p.attachments || []).map((a) => this._normalizeAttachment(a)).filter(Boolean),
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
  }

  onPostCmdClick(ev) {
    const cmd = ev.currentTarget?.dataset?.cmd;
    if (!cmd) return;

    this.postEditorRef?.el?.focus?.();

    if (cmd === "createLink") {
      const url = window.prompt("Nhập link (https://...):");
      if (url) document.execCommand("createLink", false, url);
    } else {
      document.execCommand(cmd, false, null);
    }

    this.state.ui.postHtml = this.postEditorRef?.el?.innerHTML || "";
  }

  togglePostEmoji() {
    this.state.ui.postEmojiOpen = !this.state.ui.postEmojiOpen;
  }

  onInsertPostEmoji(ev) {
    const emoji = ev.currentTarget?.dataset?.emoji;
    if (!emoji) return;

    this.postEditorRef?.el?.focus?.();
    document.execCommand("insertText", false, emoji);
    this.state.ui.postHtml = this.postEditorRef?.el?.innerHTML || "";
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
      return this.notification.add("Bạn chưa nhập nội dung hoặc chưa đính kèm file.", { type: "warning" });
    }
    if (!this.state.selectedChannelId) return;

    let bodyHtml = (this.state.ui.postHtml || "").trim();
    if (!bodyHtml) bodyHtml = "<p></p>"; // allow only-file post

    if (this.state.ui.composerMode === "announcement") {
      const title = (this.state.ui.announcementTitle || "").trim();
      if (title) {
        const t = title.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
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
    const cur = this.state.openComments[postId];
    if (cur?.loaded) {
      delete this.state.openComments[postId];
      return;
    }

    this.state.openComments[postId] = { loaded: false, items: [] };

    const res = await this.api.comments(postId, { limit: 50, offset: 0 });
    this.state.openComments[postId] = {
      loaded: true,
      items: (res.items || [])
        .filter((x) => x && x.id)
        .map((c) => ({
          ...c,
          avatarText: this._avatarText(c.author_name),
          dateText: this._dateText(c.create_date),
          body: markup(c.body_html || ""),
          attachments: (c.attachments || []).map((a) => this._normalizeAttachment(a)).filter(Boolean),
        })),
    };
  }

  onCommentDraftInputEv(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (!postId) return;
    this.state.ui.commentDraft[postId] = ev.target.value;
  }

  onCommentEditorInput(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (!postId) return;
    this.state.ui.commentHtml[postId] = ev.currentTarget?.innerHTML || "";
  }

  _findCommentEditor(postId) {
    return this.el?.querySelector(`.ch-editor--comment[data-post-id="${postId}"]`);
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
    const open = this.state.ui.commentEmojiOpen && this.state.ui.commentEmojiTarget === postId;
    this.state.ui.commentEmojiOpen = !open;
    this.state.ui.commentEmojiTarget = open ? null : postId;
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
      this.notification.add("Không tìm thấy input comment_files (t-ref).", { type: "warning" });
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

      // ✅ comment upload: { communityId, postId }
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
    const textDraft = (this.state.ui.commentDraft?.[postId] || "").trim();

    const atts = this.state.ui.commentAttachments?.[postId] || [];
    const attachmentIds = atts.map((a) => a.id).filter(Boolean);

    let bodyHtml = htmlDraft;
    if (!bodyHtml && textDraft) bodyHtml = this._escapeTextToHtml(textDraft);
    if (!bodyHtml && attachmentIds.length) bodyHtml = "<p></p>";

    const plain = this._stripHtml(bodyHtml).replace(/\s+/g, "").trim();
    if (!plain && !attachmentIds.length) return;

    try {
      await this.api.createComment({ postId, bodyHtml, attachmentIds });
    } catch (e) {
      this.notification.add(`Gửi bình luận lỗi: ${e?.message || e}`, { type: "danger" });
      return;
    }

    // reset drafts
    this.state.ui.commentHtml[postId] = "";
    this.state.ui.commentDraft[postId] = "";
    this.state.ui.commentAttachments[postId] = [];

    const ed = this._findCommentEditor(postId);
    if (ed) ed.innerHTML = "";

    this._openCommentsRemove(postId);
await this.toggleComments(postId);

    await this.refreshFeed();
  }

  // ========= REACTIONS =========
  onReactClick(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    const emoji = ev.currentTarget?.dataset?.emoji;
    if (!postId || !emoji) return;
    const post = this.state.feed.find((p) => p.id === postId);
    if (post) this.reactPost(post, emoji);
  }

  async reactPost(post, emoji) {
    if (!this.api.toggleReaction) {
      this.notification.add("API toggleReaction chưa được khai báo.", { type: "warning" });
      return;
    }
    await this.api.toggleReaction({
      communityId: post.community_id,
      emoji,
      postId: post.id,
      commentId: null,
    });
    await this.refreshFeed();
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
    if (!name) return this.notification.add("Vui lòng nhập tên Community", { type: "warning" });

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
    if (!name) return this.notification.add("Vui lòng nhập tên Channel", { type: "warning" });

    const communityId = this.state.selectedCommunity?.id;
    if (!communityId) return this.notification.add("Bạn chưa chọn Community", { type: "warning" });

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

  // ========= PASTE (Ctrl+V) IMAGE -> ATTACHMENTS =========
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

      // ✅ FIX: comment paste upload phải dùng postId (không dùng channelId)
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
          .map((a) => this._normalizeAttachment(a))
          .filter(Boolean),
      })),
  });
}

}

registry.category("actions").add("community_hub.client_action", CommunityHubClientAction);
