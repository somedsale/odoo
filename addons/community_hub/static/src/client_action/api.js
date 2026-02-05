/** @odoo-module **/

/**
 * community_hub/client_action/api.js
 *
 * - JSON-RPC wrapper: call(route, params)
 * - Upload attachments via fetch multipart:
 *      uploadAttachments({ communityId, channelId?, postId?, files })
 */

export function makeCommunityAPI(rpc) {
  // ========= JSON RPC =========
  const call = (route, params = {}) => rpc(route, params);

  // ========= helpers =========
  const _getCsrfToken = () => {
    try {
      if (window?.odoo?.csrf_token) return window.odoo.csrf_token;
      if (window?.csrf_token) return window.csrf_token;
      if (window?.__csrf_token) return window.__csrf_token;
      const meta = document.querySelector('meta[name="csrf_token"]');
      if (meta?.content) return meta.content;
    } catch (e) {}
    return null;
  };

  const _safeJson = async (resp) => {
    const ct = (resp.headers.get("content-type") || "").toLowerCase();
    const txt = await resp.text();
    if (!txt) return null;

    if (ct.includes("application/json")) {
      try {
        return JSON.parse(txt);
      } catch (e) {}
    }

    try {
      return JSON.parse(txt);
    } catch (e) {
      const m = txt.match(/(\{[\s\S]*\}|\[[\s\S]*\])/);
      if (m) {
        try {
          return JSON.parse(m[1]);
        } catch (e2) {}
      }
    }

    return { _raw: txt };
  };

  /**
   * uploadAttachments({
   *  communityId,
   *  channelId?  -> upload cho post
   *  postId?     -> upload cho comment
   *  files: File[]
   * })
   */
  const uploadAttachments = async ({ communityId, channelId, postId, files }) => {
    if (!communityId) throw new Error("Missing communityId");

    const hasChannel = !!channelId;
    const hasPost = !!postId;
    if (!hasChannel && !hasPost) {
      throw new Error("uploadAttachments requires channelId (post) OR postId (comment).");
    }

    const form = new FormData();
    form.append("community_id", String(communityId));
    if (hasChannel) form.append("channel_id", String(channelId));
    if (hasPost) form.append("post_id", String(postId));

    const csrf = _getCsrfToken();
    if (csrf) form.append("csrf_token", csrf);

    for (const f of files || []) {
      form.append("files", f, f.name);
    }

    const resp = await fetch("/community_hub/api/attachment/upload", {
      method: "POST",
      body: form,
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });

    if (!resp.ok) {
      const err = await resp.text();
      throw new Error(`Upload failed (${resp.status}): ${err}`);
    }

    const data = await _safeJson(resp);

    if (Array.isArray(data)) return { items: data };
    if (data?.items && Array.isArray(data.items)) return data;
    return { items: data ? [data] : [] };
  };

  const deleteAttachment = (attachmentId) => {
    if (!attachmentId) return Promise.resolve();
    return call("/community_hub/api/attachment/delete", { attachmentId });
  };

  return {
    // bootstrap
    bootstrap: () => call("/community_hub/api/bootstrap"),

    // community
    createCommunity: (payload) => call("/community_hub/api/community/create", payload),
    updateCommunity: (payload) => call("/community_hub/api/community/update", payload),
    joinCommunity: (communityId) => call(`/community_hub/api/community/${communityId}/join`),

    // channels
    channels: (communityId) => call(`/community_hub/api/community/${communityId}/channels`),
    createChannel: (payload) => call("/community_hub/api/channel/create", payload),
    updateChannel: (payload) => call("/community_hub/api/channel/update", payload),
    deleteChannel: (payload) => call("/community_hub/api/channel/delete", payload),
// post
updatePost: (payload) => call("/community_hub/api/post/update", payload),
deletePost: (payload) => call("/community_hub/api/post/delete", payload),

// comment
updateComment: (payload) => call("/community_hub/api/comment/update", payload),
deleteComment: (payload) => call("/community_hub/api/comment/delete", payload),
unread: (payload) => call("/community_hub/api/unread", payload),
markChannelRead: (payload) => call("/community_hub/api/channel/mark_read", payload),

    // feed / comments
    feed: (channelId, params = {}) =>
      call("/community_hub/api/channel/feed", { channelId, ...params }),

    comments: (postId, params = {}) =>
      call(`/community_hub/api/post/${postId}/comments`, params),

    // post / comment create
    createPost: (payload) => call("/community_hub/api/post/create", payload),
    createComment: (payload) => call("/community_hub/api/comment/create", payload),

    // reactions
    toggleReaction: (payload) => call("/community_hub/api/reaction/toggle", payload),

    // members
    members: (communityId) => call(`/community_hub/api/community/${communityId}/members`),
    searchUsers: ({ communityId, q, limit }) =>
      call(`/community_hub/api/community/${communityId}/users/search`, { q, limit }),
    invite: ({ communityId, userIds }) =>
      call(`/community_hub/api/community/${communityId}/members/invite`, { userIds }),
    kick: ({ communityId, userId }) =>
      call(`/community_hub/api/community/${communityId}/members/kick`, { userId }),
    setRole: ({ communityId, userId, role }) =>
      call(`/community_hub/api/community/${communityId}/members/role`, { userId, role }),

    // attachments
    uploadAttachments,
    deleteAttachment,
  };
}
