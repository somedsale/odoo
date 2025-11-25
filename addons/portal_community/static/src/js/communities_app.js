/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class CommunitiesApp extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            communities: [],
            activeCommunityId: null,
            activeChannelId: null,

            showCommunityForm: false,
            communityForm: {
                name: "",
                description: "",
            },

            showChannelForm: false,
            channelForm: {
                name: "",
                description: "",
            },

            composer: {
                subject: "",
                body: "",
            },

            posts: [],
            newComments: {},   // { [postId]: "text" }
        });

        onWillStart(async () => {
            await this.loadInitialData();
        });
    }

    // ========== GETTERS ==========

    get activeCommunity() {
        return (
            this.state.communities.find(
                (c) => c.id === this.state.activeCommunityId
            ) || null
        );
    }

    get activeChannel() {
        const com = this.activeCommunity;
        if (!com || !com.channels) {
            return null;
        }
        return (
            com.channels.find(
                (ch) => ch.id === this.state.activeChannelId
            ) || null
        );
    }

    // ========== LOAD INITIAL DATA ==========

    async loadInitialData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "portal.community",
                "get_app_data",
                [{}]          // params = {}
            );

            this.state.communities = data.communities || [];
            this.state.activeCommunityId =
                data.active_community_id ||
                (this.state.communities[0] && this.state.communities[0].id) ||
                null;
            this.state.activeChannelId = data.active_channel_id || null;
            this.state.posts = data.posts || [];
            this.state.newComments = {};
        } catch (err) {
            console.error("loadInitialData error", err);
            this.notification.add(
                _t("Không thể tải dữ liệu cộng đồng."),
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    // ========== COMMUNITY: TẠO / CHỌN ==========

    onToggleCommunityForm() {
        this.state.showCommunityForm = !this.state.showCommunityForm;
        if (!this.state.showCommunityForm) {
            this.state.communityForm.name = "";
            this.state.communityForm.description = "";
        }
    }

    async onCreateCommunity() {
        const name = (this.state.communityForm.name || "").trim();
        if (!name) {
            this.notification.add(_t("Vui lòng nhập tên community."), {
                type: "warning",
            });
            return;
        }
        try {
            await this.orm.create("portal.community", [
                {
                    name,
                    description: this.state.communityForm.description || "",
                },
            ]);

            this.onToggleCommunityForm();
            await this.loadInitialData();
        } catch (err) {
            console.error("onCreateCommunity error", err);
            this.notification.add(_t("Không thể tạo community."), {
                type: "danger",
            });
        }
    }

    async onSelectCommunity(ev) {
        const id = Number(ev.currentTarget.dataset.communityId);
        if (!id || id === this.state.activeCommunityId) {
            return;
        }
        this.state.activeCommunityId = id;

        const com = this.state.communities.find((c) => c.id === id);
        this.state.activeChannelId =
            com && com.channels && com.channels.length
                ? com.channels[0].id
                : null;

        await this._loadPostsForActiveChannel();
    }

    // ========== CHANNEL: TẠO / CHỌN ==========

    onToggleChannelForm() {
        this.state.showChannelForm = !this.state.showChannelForm;
        if (!this.state.showChannelForm) {
            this.state.channelForm.name = "";
            this.state.channelForm.description = "";
        }
    }

    async onCreateChannel() {
        const name = (this.state.channelForm.name || "").trim();
        if (!name) {
            this.notification.add(_t("Vui lòng nhập tên channel."), {
                type: "warning",
            });
            return;
        }

        const com = this.activeCommunity;
        if (!com) {
            this.notification.add(_t("Không có community được chọn."), {
                type: "warning",
            });
            return;
        }

        try {
            await this.orm.create("portal.community.channel", [
                {
                    name,
                    description: this.state.channelForm.description || "",
                    community_id: com.id,
                },
            ]);

            this.onToggleChannelForm();
            await this.loadInitialData();
        } catch (err) {
            console.error("onCreateChannel error", err);
            this.notification.add(_t("Không thể tạo channel."), {
                type: "danger",
            });
        }
    }

    async onSelectChannel(ev) {
        const id = Number(ev.currentTarget.dataset.channelId);
        if (!id || id === this.state.activeChannelId) {
            return;
        }
        this.state.activeChannelId = id;
        await this._loadPostsForActiveChannel();
    }

    async _loadPostsForActiveChannel() {
        const channel = this.activeChannel;
        if (!channel) {
            this.state.posts = [];
            this.state.newComments = {};
            return;
        }

        try {
            const posts = await this.orm.call(
                "portal.community.post",
                "get_posts_for_channel",
                [channel.id]
            );
            this.state.posts = posts || [];
            this.state.newComments = {};
        } catch (err) {
            console.error("_loadPostsForActiveChannel error", err);
            this.notification.add(_t("Không thể tải bài viết."), {
                type: "danger",
            });
        }
    }

    // ========== POST ==========

    async onSubmitPost() {
        const com = this.activeCommunity;
        const ch = this.activeChannel;
        if (!com || !ch) {
            return;
        }

        const subject = (this.state.composer.subject || "").trim();
        const body = (this.state.composer.body || "").trim();

        if (!subject && !body) {
            this.notification.add(_t("Vui lòng nhập nội dung bài viết."), {
                type: "warning",
            });
            return;
        }

        const vals = {
            community_id: com.id,
            channel_id: ch.id,
            subject,
            body,
            body_html: "", // server sẽ tự dựng nếu cần
        };

        try {
            const post = await this.orm.call(
                "portal.community.post",
                "create_from_portal",
                [vals]
            );
            // prepend
            this.state.posts.unshift(post);
            this.state.composer.subject = "";
            this.state.composer.body = "";
        } catch (err) {
            console.error("onSubmitPost error", err);
            this.notification.add(_t("Không thể tạo bài viết."), {
                type: "danger",
            });
        }
    }

    // ========== COMMENT ==========

    onChangeComment(ev) {
        const postId = Number(ev.target.dataset.postId);
        if (!postId) {
            return;
        }
        this.state.newComments[postId] = ev.target.value;
    }

    async onSubmitComment(ev) {
        const postId = Number(ev.currentTarget.dataset.postId);
        if (!postId) {
            return;
        }
        const body = (this.state.newComments[postId] || "").trim();
        if (!body) {
            return;
        }

        const vals = {
            post_id: postId,
            body,
        };

        try {
            const comment = await this.orm.call(
                "portal.community.comment",
                "create_from_portal",
                [vals]
            );

            const post = this.state.posts.find((p) => p.id === postId);
            if (post) {
                if (!post.comments) {
                    post.comments = [];
                }
                post.comments.push(comment);
            }

            this.state.newComments[postId] = "";
        } catch (err) {
            console.error("onSubmitComment error", err);
            this.notification.add(_t("Không thể gửi bình luận."), {
                type: "danger",
            });
        }
    }
}

CommunitiesApp.template = "portal_community.CommunitiesApp";

registry
    .category("actions")
    .add("communities.client_action", CommunitiesApp);
