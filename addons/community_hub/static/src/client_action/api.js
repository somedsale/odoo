/** @odoo-module **/

export function makeCommunityAPI(rpc) {
  // rpc: this.env.services.rpc (function)
  return {
    // bootstrap
    bootstrap() {
      return rpc("/community_hub/api/bootstrap", {});
    },

    // community
    createCommunity(payload) {
      // payload: {name, joinPolicy, isPublic, descriptionHtml}
      return rpc("/community_hub/api/community/create", payload);
    },
    updateCommunity(payload) {
      // payload: {communityId, vals}
      return rpc("/community_hub/api/community/update", payload);
    },
    joinCommunity(communityId) {
      return rpc(`/community_hub/api/community/${communityId}/join`, {});
    },

    // channels
    channels(communityId) {
      return rpc(`/community_hub/api/community/${communityId}/channels`, {});
    },
    createChannel(payload) {
      // payload: {communityId, name, sequence}
      return rpc("/community_hub/api/channel/create", payload);
    },
    updateChannel(payload) {
      // payload: {channelId, vals}
      return rpc("/community_hub/api/channel/update", payload);
    },
    deleteChannel(payload) {
      // payload: {channelId}
      return rpc("/community_hub/api/channel/delete", payload);
    },

    // feed
    feed(channelId, opts = {}) {
      const { limit = 20, offset = 0 } = opts;
      return rpc(`/community_hub/api/channel/${channelId}/feed`, { limit, offset });
    },
    // alias (phòng khi đâu đó gọi dạng /channel/feed)
    feedAlias(channelId, opts = {}) {
      const { limit = 20, offset = 0 } = opts;
      return rpc("/community_hub/api/channel/feed", { channelId, limit, offset });
    },

    // posts
    createPost(payload) {
      // payload: {channelId, bodyHtml, attachmentIds: []}
      return rpc("/community_hub/api/post/create", payload);
    },

    // comments
    comments(postId, opts = {}) {
      const { limit = 50, offset = 0 } = opts;
      return rpc(`/community_hub/api/post/${postId}/comments`, { limit, offset });
    },
    createComment(payload) {
      // payload: {postId, bodyHtml, attachmentIds: []}
      return rpc("/community_hub/api/comment/create", payload);
    },

    // reactions
    toggleReaction(payload) {
      // payload: {communityId, emoji, postId, commentId}
      return rpc("/community_hub/api/reaction/toggle", payload);
    },

    // members
    members(communityId) {
      return rpc(`/community_hub/api/community/${communityId}/members`, {});
    },
    searchUsers({ communityId, q, limit = 10 }) {
      return rpc(`/community_hub/api/community/${communityId}/users/search`, { q, limit });
    },
    invite({ communityId, userIds }) {
      return rpc(`/community_hub/api/community/${communityId}/members/invite`, { userIds });
    },
    kick({ communityId, userId }) {
      return rpc(`/community_hub/api/community/${communityId}/members/kick`, { userId });
    },
    setRole({ communityId, userId, role }) {
      return rpc(`/community_hub/api/community/${communityId}/members/role`, { userId, role });
    },
  };
}
