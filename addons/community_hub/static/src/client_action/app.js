/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, onWillUnmount, useState, markup } from "@odoo/owl";
import { makeCommunityAPI } from "@community_hub/client_action/api";

console.log("[community_hub] app.js loaded ✅");

export class CommunityHubClientAction extends Component {
  static template = "community_hub.ClientAction";

  setup() {
    this.bus = this.env.services.bus_service;
    this.notification = this.env.services.notification;
    this.rpc = this.env.services.rpc;
    this.api = makeCommunityAPI(this.rpc);

    this._busStarted = false;
    this._busCommunityId = null;

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

      ui: {
        activeTab: "posts",

        composerMode: "post",
        announcementTitle: "",
        postDraft: "",
        commentDraft: {},

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

    this._onBusNotification = (ev) => {
      const raw = ev?.detail;
      const list = Array.isArray(raw) ? raw : Array.isArray(raw?.notifications) ? raw.notifications : [];
      for (const n of list) {
        const payload = Array.isArray(n) ? n[1] : (n?.payload ?? n?.message ?? n);
        if (!payload?.type) continue;

        if (payload.type === "bootstrap_reload" || payload.type === "invited" || payload.type === "kicked") {
          this.loadBootstrap();
          continue;
        }

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
        this.bus.start();
      }
      this._syncBusChannels();
    });

    onWillUnmount(() => {
      if (this._busStarted) {
        this.bus.removeEventListener("notification", this._onBusNotification);
      }
    });
  }

  // ================== GETTERS ==================
  get canManage() {
    return ["owner", "admin"].includes(this.state.ui.myRole);
  }

  get selectedChannel() {
    return this.state.channels.find((c) => c.id === this.state.selectedChannelId) || null;
  }

  get flattenFiles() {
    const out = [];
    for (const p of this.state.feed) {
      for (const a of p.attachments || []) {
        out.push({ key: `p${p.id}-a${a.id}`, name: a.name, url: a.url, from: `${p.author_name}` });
      }
    }
    return out;
  }

  get flattenPhotos() {
    const out = [];
    for (const p of this.state.feed) {
      for (const a of p.attachments || []) {
        if ((a.mimetype || "").startsWith("image/")) out.push({ key: `p${p.id}-a${a.id}`, url: a.url });
      }
    }
    return out;
  }

  // ================== SAFE RESET ==================
  _resetSelection({ keepCommunities = true } = {}) {
    if (!keepCommunities) this.state.communities = [];
    this.state.selectedCommunity = null;

    this.state.channels = [];
    this.state.selectedChannelId = null;

    this.state.feed = [];
    this.state.feedOffset = 0;
    this.state.feedHasMore = false;
    this.state.openComments = {};

    this.state.ui.postDraft = "";
    this.state.ui.announcementTitle = "";
    this.state.ui.commentDraft = {};
    this.state.ui.settingsOpen = false;
    this.state.ui.myRole = null;

    this._syncBusChannels();
  }

  // ================== BUS ==================
  _syncBusChannels() {
    if (!this._busStarted) return;

    if (this.state.user?.id) {
      try { this.bus.addChannel("community_hub.user", this.state.user.id); } catch (e) {}
    }

    const newCid = this.state.selectedCommunity?.id || null;
    if (this._busCommunityId && this._busCommunityId !== newCid) {
      try { this.bus.deleteChannel("community_hub", this._busCommunityId); } catch (e) {}
    }
    if (newCid) {
      try { this.bus.addChannel("community_hub", newCid); } catch (e) {}
    }
    this._busCommunityId = newCid;
  }

  // ================== UI HELPERS ==================
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

  setActiveTab(tab) {
    this.state.ui.activeTab = tab;
  }

  setComposerMode(mode) {
    this.state.ui.composerMode = mode;
  }

  // ===== XML HANDLERS (NO ARROW) =====
  onTabClick(ev) {
    const tab = ev.currentTarget?.dataset?.tab;
    if (tab) this.setActiveTab(tab);
  }

  onComposerModeClick(ev) {
    const mode = ev.currentTarget?.dataset?.mode;
    if (mode) this.setComposerMode(mode);
  }

  onToggleCommentsClick(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (postId) this.toggleComments(postId);
  }

  onReactClick(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    const emoji = ev.currentTarget?.dataset?.emoji;
    if (!postId || !emoji) return;
    const post = this.state.feed.find((p) => p.id === postId);
    if (post) this.reactPost(post, emoji);
  }

  onCommentDraftInputEv(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (!postId) return;
    this.state.ui.commentDraft[postId] = ev.target.value;
  }

  onSubmitCommentClick(ev) {
    const postId = parseInt(ev.currentTarget?.dataset?.postId || "0", 10);
    if (postId) this.submitComment(postId);
  }

  onSettingsTabClick(ev) {
    const tab = ev.currentTarget?.dataset?.tab;
    if (tab) this.setTab(tab);
  }

  onInviteClick(ev) {
    const uid = parseInt(ev.currentTarget?.dataset?.userId || "0", 10);
    if (!uid) return;
    const u = this.state.ui.memberResults.find((x) => x.id === uid);
    if (u) this.inviteUser(u);
  }

  onKickClick(ev) {
    const uid = parseInt(ev.currentTarget?.dataset?.userId || "0", 10);
    if (!uid) return;
    const m = this.state.ui.members.find((x) => x.user_id === uid);
    if (m) this.kickMember(m);
  }

  onRoleChange(ev) {
    const uid = parseInt(ev.currentTarget?.dataset?.userId || "0", 10);
    const role = ev.target.value;
    if (!uid || !role) return;
    const m = this.state.ui.members.find((x) => x.user_id === uid);
    if (m) this.changeRole(m, role);
  }

  // ================== BOOTSTRAP (FIX NO COMMUNITY) ==================
  async loadBootstrap() {
    try {
      this.state.loading = true;

      const data = await this.api.bootstrap();
      this.state.user = data.user || null;

      // ALWAYS override communities list from server
      this.state.communities = data.communities || [];
      this.state.selectedCommunity = data.selected || null;

      // ✅ FIX: if no selected community -> reset everything and stop here
      if (!this.state.selectedCommunity || !this.state.communities.length) {
        this._resetSelection({ keepCommunities: true });
        this.state.loading = false;
        return;
      }

      // channels only meaningful when selectedCommunity exists
      this.state.channels = data.channels || [];
      this.state.selectedChannelId = this.state.channels[0]?.id || null;

      // if still no channel -> reset feed area only
      this.state.feed = [];
      this.state.feedOffset = 0;
      this.state.feedHasMore = false;
      this.state.openComments = {};
      this.state.ui.postDraft = "";
      this.state.ui.commentDraft = {};
      this.state.ui.settingsOpen = false;
      this.state.ui.myRole = this.state.selectedCommunity?.my_role || null;

      this.state.loading = false;
      this._syncBusChannels();

      if (this.state.selectedCommunity && this.state.selectedChannelId) {
        await this.refreshFeed();
      }
    } catch (e) {
      this.state.loading = false;
      this.notification.add(`Bootstrap error: ${e?.message || e}`, { type: "danger" });
      this._resetSelection({ keepCommunities: false });
    }
  }

  // ================== COMMUNITY / CHANNEL SELECT ==================
  async selectCommunity(evOrObj) {
    let id = null;
    if (evOrObj?.currentTarget?.dataset?.communityId) {
      id = parseInt(evOrObj.currentTarget.dataset.communityId, 10);
    } else if (typeof evOrObj === "number") {
      id = evOrObj;
    } else if (evOrObj?.id) {
      id = evOrObj.id;
    }
    if (!id) return;

    const c = this.state.communities.find((x) => x.id === id);
    if (!c) return;

    this.state.selectedCommunity = c;
    this.state.ui.settingsOpen = false;
    this.state.ui.myRole = c.my_role || null;

    await this.reloadChannels();

    this.state.selectedChannelId = this.state.channels[0]?.id || null;
    this.state.feed = [];
    this.state.feedOffset = 0;
    this.state.feedHasMore = false;
    this.state.openComments = {};
    this.state.ui.postDraft = "";
    this.state.ui.commentDraft = {};

    this._syncBusChannels();

    if (this.state.selectedCommunity && this.state.selectedChannelId) {
      await this.refreshFeed();
    }
  }

  async selectChannel(evOrId) {
    let id = null;
    if (evOrId?.currentTarget?.dataset?.channelId) {
      id = parseInt(evOrId.currentTarget.dataset.channelId, 10);
    } else if (typeof evOrId === "number") {
      id = evOrId;
    } else if (evOrId?.id) {
      id = evOrId.id;
    }
    if (!id) return;

    // ✅ guard: must have a selected community
    if (!this.state.selectedCommunity) {
      this._resetSelection({ keepCommunities: true });
      return;
    }

    this.state.selectedChannelId = id;
    this.state.feed = [];
    this.state.feedOffset = 0;
    this.state.feedHasMore = false;
    this.state.openComments = {};
    this.state.ui.postDraft = "";
    this.state.ui.commentDraft = {};

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

  // ================== FEED (TRY/CATCH ACCESS) ==================
  async refreshFeed() {
    if (!this.state.selectedCommunity || !this.state.selectedChannelId) return;

    try {
      const res = await this.api.feed(this.state.selectedChannelId, { limit: 20, offset: 0 });
      const comm = this.state.selectedCommunity;

      const items = (res.items || []).map((p) => ({
        ...p,
        is_owner: comm?.owner_id && p.author_id === comm.owner_id,
        avatarText: this._avatarText(p.author_name),
        dateText: this._dateText(p.create_date),
        body: markup(p.body_html || ""),
        attachments: p.attachments || [],
        reactions: p.reactions || [],
      }));

      this.state.feed = items;
      this.state.feedOffset = items.length;
      this.state.feedHasMore = !!res.has_more;
    } catch (e) {
      // ✅ if server says access denied => reset selection and show soft message
      this.notification.add("Bạn không có quyền truy cập community/kênh này (hoặc đã bị kick).", { type: "warning" });
      await this.loadBootstrap(); // reload list which should hide inaccessible communities
    }
  }

  async loadMore() {
    if (!this.state.selectedCommunity || !this.state.selectedChannelId || !this.state.feedHasMore) return;

    try {
      const res = await this.api.feed(this.state.selectedChannelId, { limit: 20, offset: this.state.feedOffset });
      const comm = this.state.selectedCommunity;

      const items = (res.items || []).map((p) => ({
        ...p,
        is_owner: comm?.owner_id && p.author_id === comm.owner_id,
        avatarText: this._avatarText(p.author_name),
        dateText: this._dateText(p.create_date),
        body: markup(p.body_html || ""),
        attachments: p.attachments || [],
        reactions: p.reactions || [],
      }));

      this.state.feed.push(...items);
      this.state.feedOffset += items.length;
      this.state.feedHasMore = !!res.has_more;
    } catch (e) {
      this.notification.add("Không thể tải thêm (có thể bạn không còn quyền).", { type: "warning" });
      await this.loadBootstrap();
    }
  }

  // ================== CREATE COMMUNITY ==================
  toggleNewCommunity() {
    this.state.ui.showNewCommunity = !this.state.ui.showNewCommunity;
    if (!this.state.ui.showNewCommunity) {
      this.state.ui.newCommunityName = "";
      this.state.ui.newCommunityPublic = false;
      this.state.ui.newCommunityPolicy = "invite";
    }
  }

  onNewCommunityKeydown(ev) {
    if (ev.key === "Enter") { ev.preventDefault(); this.submitNewCommunity(); }
    if (ev.key === "Escape") { ev.preventDefault(); this.toggleNewCommunity(); }
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

  // ================== CREATE CHANNEL ==================
  toggleNewChannel() {
    if (!this.canManage) return;
    this.state.ui.showNewChannel = !this.state.ui.showNewChannel;
    if (!this.state.ui.showNewChannel) this.state.ui.newChannelName = "";
  }

  onNewChannelKeydown(ev) {
    if (ev.key === "Enter") { ev.preventDefault(); this.submitNewChannel(); }
    if (ev.key === "Escape") { ev.preventDefault(); this.toggleNewChannel(); }
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
    if (created?.id) await this.selectChannel(created.id);
  }

  // ================== POSTS / COMMENTS ==================
  async submitPost() {
    const text = (this.state.ui.postDraft || "").trim();
    if (!text) return this.notification.add("Bạn chưa nhập nội dung bài viết", { type: "warning" });
    if (!this.state.selectedCommunity || !this.state.selectedChannelId) return;

    const safe = text
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll("\n", "<br/>");

    let bodyHtml = `<p>${safe}</p>`;
    if (this.state.ui.composerMode === "announcement") {
      const title = (this.state.ui.announcementTitle || "").trim();
      if (title) {
        const t = title.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
        bodyHtml = `<h3>${t}</h3>${bodyHtml}`;
      }
    }

    await this.api.createPost({ channelId: this.state.selectedChannelId, bodyHtml, attachmentIds: [] });

    this.state.ui.postDraft = "";
    this.state.ui.announcementTitle = "";
    this.state.ui.composerMode = "post";
    await this.refreshFeed();
  }

  async toggleComments(postId) {
    const cur = this.state.openComments[postId];
    if (cur?.loaded) {
      delete this.state.openComments[postId];
      return;
    }
    const res = await this.api.comments(postId, { limit: 50, offset: 0 });
    this.state.openComments[postId] = {
      loaded: true,
      items: (res.items || []).map((c) => ({
        ...c,
        avatarText: this._avatarText(c.author_name),
        dateText: this._dateText(c.create_date),
        body: markup(c.body_html || ""),
      })),
    };
  }

  async submitComment(postId) {
    const text = (this.state.ui.commentDraft[postId] || "").trim();
    if (!text) return;

    const safe = text
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll("\n", "<br/>");

    const bodyHtml = `<p>${safe}</p>`;
    await this.api.createComment({ postId, bodyHtml, attachmentIds: [] });

    this.state.ui.commentDraft[postId] = "";
    delete this.state.openComments[postId];
    await this.toggleComments(postId);
    await this.refreshFeed();
  }

  async reactPost(post, emoji) {
    await this.api.toggleReaction({
      communityId: post.community_id,
      emoji,
      postId: post.id,
      commentId: null,
    });
    await this.refreshFeed();
  }

  // ================== SETTINGS / MEMBERS ==================
  async toggleSettings() {
    if (!this.state.selectedCommunity) return;
    this.state.ui.settingsOpen = !this.state.ui.settingsOpen;
    if (this.state.ui.settingsOpen) await this.loadManageData();
  }

  setTab(tab) {
    this.state.ui.settingsTab = tab;
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
    const res = await this.api.searchUsers({ communityId: this.state.selectedCommunity.id, q, limit: 10 });
    this.state.ui.memberResults = res.items || [];
  }

  async inviteUser(u) {
    if (!this.canManage) return;
    await this.api.invite({ communityId: this.state.selectedCommunity.id, userIds: [u.id] });
    await this.loadManageData();
  }

  async kickMember(m) {
    if (!this.canManage) return;
    await this.api.kick({ communityId: this.state.selectedCommunity.id, userId: m.user_id });
    await this.loadManageData();
  }

  async changeRole(m, role) {
    if (!this.canManage) return;
    await this.api.setRole({ communityId: this.state.selectedCommunity.id, userId: m.user_id, role });
    await this.loadManageData();
  }

  async saveCommunitySettings() {
    if (!this.canManage) return;
    await this.api.updateCommunity({ communityId: this.state.selectedCommunity.id, vals: { ...this.state.ui.communityForm } });
    await this.loadBootstrap();
    this.state.ui.settingsOpen = true;
    await this.loadManageData();
  }

  async saveChannelSettings() {
    if (!this.canManage || !this.state.selectedChannelId) return;
    await this.api.updateChannel({ channelId: this.state.selectedChannelId, vals: { ...this.state.ui.channelForm } });
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
}

registry.category("actions").add("community_hub.client_action", CommunityHubClientAction);
