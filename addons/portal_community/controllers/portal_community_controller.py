# portal_community/controllers/portal_community_controller.py
from odoo import http
from odoo.http import request
from odoo.tools import format_datetime


class PortalCommunityController(http.Controller):

    # ==== Helpers serialize ====

    def _serialize_comment(self, comment):
        return {
            "id": comment.id,
            "author_name": comment.author_id.name if comment.author_id else "",
            "author_initials": (comment.author_id.name or "")[:2].upper()
                if comment.author_id and comment.author_id.name else "",
            "create_date": comment.create_date,
            "create_date_human": format_datetime(
                request.env, comment.create_date, tz=request.env.user.tz or "UTC"
            ),
            "body": comment.body or "",
            "body_html": comment.body_html or "",
        }

    def _serialize_post(self, post):
        return {
            "id": post.id,
            "subject": post.subject or "",
            "body": post.body or "",
            "body_html": post.body_html or "",
            "author_name": post.author_id.name if post.author_id else "",
            "author_initials": (post.author_id.name or "")[:2].upper()
                if post.author_id and post.author_id.name else "",
            "create_date": post.create_date,
            "create_date_human": format_datetime(
                request.env, post.create_date, tz=request.env.user.tz or "UTC"
            ),
            "comments": [self._serialize_comment(c) for c in post.comment_ids],
        }

    def _serialize_channel(self, channel, with_posts=False):
        data = {
            "id": channel.id,
            "name": channel.name,
            "description": channel.description or "",
            "post_count": len(channel.post_ids),
        }
        if with_posts:
            data["posts"] = [self._serialize_post(p) for p in channel.post_ids]
        return data

    def _serialize_community(self, community, with_channels=False, with_posts=False):
        data = {
            "id": community.id,
            "name": community.name,
            "description": community.description or "",
            "member_count": len(community.member_ids),
            "initials": (community.name or "")[:2].upper() if community.name else "",
        }
        if with_channels:
            data["channels"] = [
                self._serialize_channel(ch, with_posts=with_posts)
                for ch in community.channel_ids
            ]
        return data

    # ==== API ====

    @http.route(
        "/portal_community/communities",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def get_communities(self, **kwargs):
        """Load list communities for current user (simple version: all)."""
        Community = request.env["portal.community"].sudo()
        communities = Community.search([], order="name")
        return {
            "communities": [
                self._serialize_community(c, with_channels=True, with_posts=False)
                for c in communities
            ]
        }

    @http.route(
        "/portal_community/community/create",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def create_community(self, vals=None, **kwargs):
        vals = vals or {}
        Community = request.env["portal.community"].sudo()
        partner = request.env.user.partner_id

        community = Community.create({
            "name": vals.get("name"),
            "description": vals.get("description"),
            "member_ids": [(4, partner.id)] if partner else False,
        })
        return self._serialize_community(community, with_channels=True)

    @http.route(
        "/portal_community/community/detail",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def community_detail(self, community_id=None, **kwargs):
        Community = request.env["portal.community"].sudo()
        community = Community.browse(int(community_id))
        if not community.exists():
            return {}
        return self._serialize_community(community, with_channels=True, with_posts=False)

    @http.route(
        "/portal_community/channel/create",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def create_channel(self, community_id=None, vals=None, **kwargs):
        vals = vals or {}
        Channel = request.env["portal.community.channel"].sudo()
        community_id = int(community_id) if community_id else False

        channel = Channel.create({
            "name": vals.get("name"),
            "description": vals.get("description"),
            "community_id": community_id,
        })
        return self._serialize_channel(channel)

    @http.route(
        "/portal_community/channel/posts",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def channel_posts(self, channel_id=None, **kwargs):
        Post = request.env["portal.community.post"].sudo()
        channel_id = int(channel_id) if channel_id else False
        posts = Post.search([("channel_id", "=", channel_id)], order="create_date desc")
        return {
            "posts": [self._serialize_post(p) for p in posts],
        }

    @http.route(
        "/portal_community/post/create",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def create_post(self, channel_id=None, vals=None, **kwargs):
        vals = vals or {}
        Post = request.env["portal.community.post"].sudo()
        user = request.env.user

        channel_id = int(channel_id) if channel_id else False

        post = Post.create({
            "channel_id": channel_id,
            "author_id": user.partner_id.id if user.partner_id else False,
            "subject": vals.get("subject"),
            "body": vals.get("body"),
            "body_html": vals.get("body_html") or vals.get("body"),
        })
        return self._serialize_post(post)

    @http.route(
        "/portal_community/comment/create",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def create_comment(self, post_id=None, body=None, **kwargs):
        Comment = request.env["portal.community.comment"].sudo()
        Post = request.env["portal.community.post"].sudo()
        user = request.env.user

        post = Post.browse(int(post_id)) if post_id else Post.browse()
        if not post:
            return {}

        comment = Comment.create({
            "post_id": post.id,
            "author_id": user.partner_id.id if user.partner_id else False,
            "body": body,
            "body_html": body,
        })
        return self._serialize_comment(comment)