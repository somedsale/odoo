# -*- coding: utf-8 -*-
from odoo import _, http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

# =========================================================
# BUS HELPERS (chịu nhiều signature _sendone khác nhau)
# =========================================================
def _bus_send(channel_name: str, channel_id: int, payload: dict):
    """Send payload to bus channel used by bus_service.addChannel(name, id)."""
    bus = request.env["bus.bus"].sudo()
    dbname = request.env.cr.dbname
    channel_id = int(channel_id)
    payload = payload or {}

    full = (dbname, channel_name, channel_id)
    short = (channel_name, channel_id)

    # try patterns (versions differ)
    for args in (
        (full, payload),              # Odoo 17 style often works
        (dbname, short, payload),
        (dbname, full, payload),
        (short, payload),
    ):
        try:
            bus._sendone(*args)
            return
        except TypeError:
            continue
        except Exception:
            _logger.exception("bus _sendone failed args=%s", args)
            return


def _notify_community(community_id: int, payload: dict):
    _bus_send("community_hub", int(community_id), payload)


def _notify_user(user_id: int, payload: dict):
    _bus_send("community_hub.user", int(user_id), payload)


# =========================================================
# ACCESS HELPERS
# =========================================================
def _get_member(community_id: int, user_id: int):
    Member = request.env["community.hub.member"].sudo()
    return Member.search([("community_id", "=", int(community_id)), ("user_id", "=", int(user_id))], limit=1)


def _ensure_access_community(community_id: int):
    """
    User phải có member record (joined/invited) thì mới access được community.
    Nếu bị kick => record bị xoá => coi như không có quyền.
    """
    community_id = int(community_id)
    community = request.env["community.hub"].sudo().browse(community_id)
    if not community.exists():
        raise ValidationError(_("Community not found."))

    m = _get_member(community_id, request.env.user.id)
    if not m or m.state not in ("joined", "invited"):
        raise AccessError(_("You are not allowed to access this community."))

    return community, m


def _ensure_joined(community_id: int):
    community, m = _ensure_access_community(community_id)
    if m.state != "joined":
        raise AccessError(_("You must join this community to do this action."))
    return community, m


def _ensure_manage(community_id: int):
    community, m = _ensure_joined(community_id)
    if m.role not in ("owner", "admin"):
        raise AccessError(_("You are not allowed to manage this community."))
    return community, m


def _ensure_owner(community_id: int):
    community, m = _ensure_joined(community_id)
    if m.role != "owner":
        raise AccessError(_("Only owner can do this action."))
    return community, m


# =========================================================
# SERIALIZERS
# =========================================================
def _community_to_dict(c, my_member=None):
    return {
        "id": c.id,
        "name": c.name,
        "owner_id": c.owner_id.id if c.owner_id else False,
        "join_policy": c.join_policy,
        "is_public": bool(getattr(c, "is_public", False)),
        "description_html": c.description_html or "",
        "my_role": my_member.role if my_member else None,
        "my_state": my_member.state if my_member else None,
    }


def _channel_to_dict(ch):
    return {"id": ch.id, "name": ch.name, "community_id": ch.community_id.id, "sequence": ch.sequence}


def _attachment_to_dict(a):
    return {
        "id": a.id,
        "name": a.name,
        "mimetype": a.mimetype,
        "url": f"/web/content/{a.id}?download=true",
    }


def _reaction_summary(post_id=None, comment_id=None):
    Reaction = request.env["community.hub.reaction"].sudo()
    dom = []
    if post_id:
        dom += [("post_id", "=", int(post_id))]
    else:
        dom += [("post_id", "=", False)]
    if comment_id:
        dom += [("comment_id", "=", int(comment_id))]
    else:
        dom += [("comment_id", "=", False)]

    recs = Reaction.search(dom)
    me_uid = request.env.user.id
    summary = {}
    for r in recs:
        e = r.emoji or ""
        if not e:
            continue
        if e not in summary:
            summary[e] = {"count": 0, "me": False}
        summary[e]["count"] += 1
        if r.user_id.id == me_uid:
            summary[e]["me"] = True
    # output as list for easy render
    out = []
    for emoji, d in summary.items():
        out.append({"emoji": emoji, "count": d["count"], "me": d["me"]})
    return out


def _post_to_dict(p):
    atts = []
    if "attachment_ids" in p._fields:
        atts = [_attachment_to_dict(a) for a in p.attachment_ids]
    return {
        "id": p.id,
        "community_id": p.community_id.id,
        "channel_id": p.channel_id.id,
        "author_id": p.author_id.id if p.author_id else False,
        "author_name": p.author_id.name if p.author_id else "",
        "body_html": p.body_html or "",
        "create_date": p.create_date,
        "attachments": atts,
        "reactions": _reaction_summary(post_id=p.id),
    }


def _comment_to_dict(c):
    atts = []
    if "attachment_ids" in c._fields:
        atts = [_attachment_to_dict(a) for a in c.attachment_ids]
    return {
        "id": c.id,
        "post_id": c.post_id.id,
        "community_id": c.community_id.id if "community_id" in c._fields else c.post_id.community_id.id,
        "author_id": c.author_id.id if c.author_id else False,
        "author_name": c.author_id.name if c.author_id else "",
        "body_html": c.body_html or "",
        "create_date": c.create_date,
        "attachments": atts,
        "reactions": _reaction_summary(comment_id=c.id),
    }


# =========================================================
# CONTROLLER
# =========================================================
class CommunityHubController(http.Controller):

    # ---------------- BOOTSTRAP ----------------
    @http.route("/community_hub/api/bootstrap", type="json", auth="user")
    def bootstrap(self):
        user = request.env.user
        Member = request.env["community.hub.member"].sudo()

        # ✅ Chỉ community mà user JOINED/INVITED
        my_members = Member.search([
            ("user_id", "=", user.id),
            ("state", "in", ["joined", "invited"]),
        ])

        communities = my_members.mapped("community_id").sorted(key=lambda x: (x.id), reverse=True)
        selected = communities[:1]
        selected = selected[0] if selected else None

        channels = request.env["community.hub.channel"].sudo().search(
            [("community_id", "=", selected.id)] if selected else [],
            order="sequence,id",
        )

        def _my_member_for(c):
            return my_members.filtered(lambda m: m.community_id.id == c.id)[:1]

        return {
            "user": {"id": user.id, "name": user.name, "login": user.login},
            "communities": [_community_to_dict(c, _my_member_for(c)) for c in communities],
            "selected": _community_to_dict(selected, _my_member_for(selected)) if selected else None,
            "channels": [_channel_to_dict(ch) for ch in channels],
        }

    # ---------------- COMMUNITY CRUD ----------------
    @http.route("/community_hub/api/community/create", type="json", auth="user")
    def create_community(self, name=None, joinPolicy="invite", isPublic=False, descriptionHtml=None, **kw):
        # unwrap nếu JS bọc sai
        if isinstance(name, dict):
            data = name
            name = data.get("name")
            joinPolicy = data.get("joinPolicy", joinPolicy)
            isPublic = data.get("isPublic", isPublic)
            descriptionHtml = data.get("descriptionHtml", descriptionHtml)

        name = (name or "").strip()
        if not name:
            raise ValidationError(_("Community name is required."))

        user = request.env.user
        Community = request.env["community.hub"].sudo()
        Member = request.env["community.hub.member"].sudo()
        Channel = request.env["community.hub.channel"].sudo()

        c = Community.create({
            "name": name,
            "owner_id": user.id,
            "join_policy": joinPolicy or "invite",
            "is_public": bool(isPublic),
            "description_html": descriptionHtml or False,
        })

        # ✅ UPSERT owner member tránh duplicate unique
        m = Member.search([("community_id", "=", c.id), ("user_id", "=", user.id)], limit=1)
        vals = {"role": "owner", "state": "joined", "invited_by": user.id}
        if m:
            m.write(vals)
        else:
            Member.create({"community_id": c.id, "user_id": user.id, **vals})

        # default channel
        # chỉ tạo nếu community chưa có channel nào
        if not Channel.search([("community_id", "=", c.id)], limit=1):
            Channel.create({"community_id": c.id, "name": "General", "sequence": 10})


        _notify_user(user.id, {"type": "bootstrap_reload"})
        return {"community": _community_to_dict(c, _get_member(c.id, user.id))}

    @http.route("/community_hub/api/community/update", type="json", auth="user")
    def update_community(self, communityId=None, vals=None, **kw):
        if isinstance(communityId, dict):
            data = communityId
            communityId = data.get("communityId") or data.get("community_id")
            vals = data.get("vals") or vals

        communityId = int(communityId or 0)
        if not communityId:
            raise ValidationError(_("communityId is required."))
        _ensure_manage(communityId)

        allowed = {"name", "join_policy", "is_public", "description_html"}
        clean = {k: v for k, v in (vals or {}).items() if k in allowed}

        request.env["community.hub"].sudo().browse(communityId).write(clean)
        _notify_community(communityId, {"type": "community_updated", "community_id": communityId})
        return {"ok": True}

    @http.route("/community_hub/api/community/<int:community_id>/join", type="json", auth="user")
    def join(self, community_id):
        community_id = int(community_id)
        community = request.env["community.hub"].sudo().browse(community_id)
        if not community.exists():
            raise ValidationError(_("Community not found."))

        user = request.env.user
        Member = request.env["community.hub.member"].sudo()

        m = Member.search([("community_id", "=", community_id), ("user_id", "=", user.id)], limit=1)

        # policy invite: phải có invited
        if community.join_policy == "invite":
            if not m or m.state != "invited":
                raise AccessError(_("You are not invited to this community."))

        if not m:
            Member.create({
                "community_id": community_id,
                "user_id": user.id,
                "role": "member",
                "state": "joined",
                "invited_by": user.id,
            })
        else:
            m.write({"state": "joined"})

        _notify_user(user.id, {"type": "bootstrap_reload"})
        _notify_community(community_id, {"type": "members_changed", "community_id": community_id})
        return {"ok": True}

    # ---------------- CHANNELS ----------------
    @http.route("/community_hub/api/community/<int:community_id>/channels", type="json", auth="user")
    def channels(self, community_id):
        _ensure_access_community(community_id)
        chs = request.env["community.hub.channel"].sudo().search(
            [("community_id", "=", int(community_id))],
            order="sequence,id",
        )
        return {"items": [_channel_to_dict(ch) for ch in chs]}

    @http.route("/community_hub/api/channel/create", type="json", auth="user")
    def create_channel(self, communityId=None, name=None, sequence=10, **kw):
        # ✅ unwrap mọi kiểu payload lỗi
        if isinstance(communityId, dict):
            data = communityId
            communityId = data.get("communityId") or data.get("community_id")
            name = data.get("name") or name
            sequence = data.get("sequence", sequence)
        else:
            if not communityId and ("communityId" in kw or "community_id" in kw):
                communityId = kw.get("communityId") or kw.get("community_id")
            if not name and "name" in kw:
                name = kw.get("name")
            if "sequence" in kw:
                sequence = kw.get("sequence", sequence)

        communityId = int(communityId or 0)
        if not communityId:
            raise ValidationError(_("communityId is required."))
        _ensure_manage(communityId)

        name = (name or "").strip()
        if not name:
            raise ValidationError(_("Channel name is required."))

        ch = request.env["community.hub.channel"].sudo().create({
            "community_id": communityId,
            "name": name,
            "sequence": int(sequence or 10),
        })
        _notify_community(communityId, {"type": "channel_created", "community_id": communityId, "channel_id": ch.id})
        return {"channel": _channel_to_dict(ch)}

    @http.route("/community_hub/api/channel/update", type="json", auth="user")
    def update_channel(self, channelId=None, vals=None, **kw):
        if isinstance(channelId, dict):
            data = channelId
            channelId = data.get("channelId") or data.get("channel_id")
            vals = data.get("vals") or vals

        channelId = int(channelId or 0)
        if not channelId:
            raise ValidationError(_("channelId is required."))

        ch = request.env["community.hub.channel"].sudo().browse(channelId)
        if not ch.exists():
            raise ValidationError(_("Channel not found."))

        _ensure_manage(ch.community_id.id)

        allowed = {"name", "sequence"}
        clean = {k: v for k, v in (vals or {}).items() if k in allowed}
        ch.write(clean)

        _notify_community(ch.community_id.id, {"type": "channel_updated", "community_id": ch.community_id.id, "channel_id": ch.id})
        return {"ok": True}

    @http.route("/community_hub/api/channel/delete", type="json", auth="user")
    def delete_channel(self, channelId=None, **kw):
        if isinstance(channelId, dict):
            data = channelId
            channelId = data.get("channelId") or data.get("channel_id")

        channelId = int(channelId or 0)
        if not channelId:
            return {"ok": True}

        ch = request.env["community.hub.channel"].sudo().browse(channelId)
        if not ch.exists():
            return {"ok": True}

        _ensure_manage(ch.community_id.id)
        cid = ch.community_id.id
        ch.unlink()

        _notify_community(cid, {"type": "channel_deleted", "community_id": cid, "channel_id": channelId})
        return {"ok": True}

    # ---------------- FEED ----------------
    @http.route("/community_hub/api/channel/<int:channel_id>/feed", type="json", auth="user")
    def feed(self, channel_id, limit=20, offset=0):
        channel_id = int(channel_id)
        ch = request.env["community.hub.channel"].sudo().browse(channel_id)
        if not ch.exists():
            raise ValidationError(_("Channel not found."))
        _ensure_access_community(ch.community_id.id)

        Post = request.env["community.hub.post"].sudo()
        posts = Post.search(
            [("channel_id", "=", channel_id)],
            order="create_date desc, id desc",
            limit=int(limit or 20),
            offset=int(offset or 0),
        )
        total = Post.search_count([("channel_id", "=", channel_id)])
        has_more = (int(offset or 0) + len(posts)) < total
        return {"items": [_post_to_dict(p) for p in posts], "has_more": has_more}

    # ✅ alias để khỏi 404 nếu JS gọi /channel/feed (không có id)
    @http.route("/community_hub/api/channel/feed", type="json", auth="user")
    def feed_alias(self, channelId=None, limit=20, offset=0, **kw):
        if isinstance(channelId, dict):
            data = channelId
            channelId = data.get("channelId") or data.get("channel_id")
            limit = data.get("limit", limit)
            offset = data.get("offset", offset)
        channelId = int(channelId or 0)
        if not channelId:
            raise ValidationError(_("channelId is required."))
        return self.feed(channelId, limit=limit, offset=offset)

    # ---------------- POSTS ----------------
    @http.route("/community_hub/api/post/create", type="json", auth="user")
    def create_post(self, channelId=None, bodyHtml=None, attachmentIds=None, **kw):
        if isinstance(channelId, dict):
            data = channelId
            channelId = data.get("channelId") or data.get("channel_id")
            bodyHtml = data.get("bodyHtml") or data.get("body_html") or bodyHtml
            attachmentIds = data.get("attachmentIds") or attachmentIds

        channelId = int(channelId or 0)
        if not channelId:
            raise ValidationError(_("channelId is required."))

        ch = request.env["community.hub.channel"].sudo().browse(channelId)
        if not ch.exists():
            raise ValidationError(_("Channel not found."))

        _ensure_joined(ch.community_id.id)

        bodyHtml = (bodyHtml or "").strip()
        if not bodyHtml:
            raise ValidationError(_("Post content is required."))

        vals = {
            "community_id": ch.community_id.id,
            "channel_id": ch.id,
            "author_id": request.env.user.id,
            "body_html": bodyHtml,
        }
        if attachmentIds and "attachment_ids" in request.env["community.hub.post"]._fields:
            vals["attachment_ids"] = [(6, 0, [int(x) for x in attachmentIds])]

        post = request.env["community.hub.post"].sudo().create(vals)
        _notify_community(ch.community_id.id, {"type": "post_created", "community_id": ch.community_id.id, "channel_id": ch.id, "post_id": post.id})
        return {"post": _post_to_dict(post)}

    # ---------------- COMMENTS ----------------
    @http.route("/community_hub/api/post/<int:post_id>/comments", type="json", auth="user")
    def comments(self, post_id, limit=50, offset=0):
        post_id = int(post_id)
        post = request.env["community.hub.post"].sudo().browse(post_id)
        if not post.exists():
            raise ValidationError(_("Post not found."))
        _ensure_access_community(post.community_id.id)

        Comment = request.env["community.hub.comment"].sudo()
        items = Comment.search(
            [("post_id", "=", post_id)],
            order="create_date asc, id asc",
            limit=int(limit or 50),
            offset=int(offset or 0),
        )
        total = Comment.search_count([("post_id", "=", post_id)])
        has_more = (int(offset or 0) + len(items)) < total

        return {"items": [_comment_to_dict(c) for c in items], "has_more": has_more}

    @http.route("/community_hub/api/comment/create", type="json", auth="user")
    def create_comment(self, postId=None, bodyHtml=None, attachmentIds=None, **kw):
        if isinstance(postId, dict):
            data = postId
            postId = data.get("postId") or data.get("post_id")
            bodyHtml = data.get("bodyHtml") or data.get("body_html") or bodyHtml
            attachmentIds = data.get("attachmentIds") or attachmentIds

        postId = int(postId or 0)
        if not postId:
            raise ValidationError(_("postId is required."))

        post = request.env["community.hub.post"].sudo().browse(postId)
        if not post.exists():
            raise ValidationError(_("Post not found."))

        _ensure_joined(post.community_id.id)

        bodyHtml = (bodyHtml or "").strip()
        if not bodyHtml:
            raise ValidationError(_("Comment content is required."))

        vals = {
            "community_id": post.community_id.id,
            "post_id": post.id,
            "author_id": request.env.user.id,
            "body_html": bodyHtml,
        }
        if attachmentIds and "attachment_ids" in request.env["community.hub.comment"]._fields:
            vals["attachment_ids"] = [(6, 0, [int(x) for x in attachmentIds])]

        c = request.env["community.hub.comment"].sudo().create(vals)
        _notify_community(post.community_id.id, {"type": "comment_created", "community_id": post.community_id.id, "post_id": post.id, "comment_id": c.id})
        return {"comment": _comment_to_dict(c)}

    # ---------------- REACTIONS ----------------
    @http.route("/community_hub/api/reaction/toggle", type="json", auth="user")
    def toggle_reaction(self, communityId=None, emoji=None, postId=None, commentId=None, **kw):
        if isinstance(communityId, dict):
            data = communityId
            communityId = data.get("communityId") or data.get("community_id")
            emoji = data.get("emoji") or emoji
            postId = data.get("postId") or postId
            commentId = data.get("commentId") or commentId

        communityId = int(communityId or 0)
        if not communityId:
            raise ValidationError(_("communityId is required."))

        _ensure_joined(communityId)

        emoji = (emoji or "").strip()
        if not emoji:
            raise ValidationError(_("Emoji is required."))

        postId = int(postId) if postId else False
        commentId = int(commentId) if commentId else False
        if not postId and not commentId:
            raise ValidationError(_("postId or commentId is required."))

        Reaction = request.env["community.hub.reaction"].sudo()
        dom = [
            ("community_id", "=", communityId),
            ("user_id", "=", request.env.user.id),
            ("emoji", "=", emoji),
            ("post_id", "=", postId or False),
            ("comment_id", "=", commentId or False),
        ]
        r = Reaction.search(dom, limit=1)
        if r:
            r.unlink()
            action = "removed"
        else:
            Reaction.create({
                "community_id": communityId,
                "user_id": request.env.user.id,
                "emoji": emoji,
                "post_id": postId or False,
                "comment_id": commentId or False,
            })
            action = "added"

        _notify_community(communityId, {"type": "reaction_toggled", "community_id": communityId, "emoji": emoji, "action": action})
        return {"ok": True}

    # ---------------- MEMBERS ----------------
    @http.route("/community_hub/api/community/<int:community_id>/members", type="json", auth="user")
    def members(self, community_id):
        _ensure_access_community(community_id)

        members = request.env["community.hub.member"].sudo().search([
            ("community_id", "=", int(community_id)),
            ("state", "in", ["joined", "invited"]),
        ], order="role desc, id asc")

        return {
            "items": [{
                "id": m.id,
                "user_id": m.user_id.id,
                "name": m.user_id.name,
                "login": m.user_id.login,
                "role": m.role,
                "state": m.state,
            } for m in members]
        }

    @http.route("/community_hub/api/community/<int:community_id>/users/search", type="json", auth="user")
    def search_users(self, community_id, q=None, limit=10):
        _ensure_manage(community_id)

        q = (q or "").strip()
        if not q:
            return {"items": []}

        existing = request.env["community.hub.member"].sudo().search([
            ("community_id", "=", int(community_id)),
            ("state", "in", ["joined", "invited"]),
        ]).mapped("user_id").ids

        Users = request.env["res.users"].sudo()
        dom = ["|", ("name", "ilike", q), ("login", "ilike", q)]
        if existing:
            dom = ["&", ("id", "not in", existing)] + dom

        users = Users.search(dom, limit=int(limit or 10))
        return {"items": [{"id": u.id, "name": u.name, "login": u.login} for u in users]}

    @http.route("/community_hub/api/community/<int:community_id>/members/invite", type="json", auth="user")
    def invite(self, community_id, userIds=None):
        _ensure_manage(community_id)
        community_id = int(community_id)

        userIds = [int(x) for x in (userIds or [])]
        if not userIds:
            return {"ok": True}

        Member = request.env["community.hub.member"].sudo()
        for uid in userIds:
            m = Member.search([("community_id", "=", community_id), ("user_id", "=", uid)], limit=1)
            if m:
                m.write({"state": "invited", "role": "member", "invited_by": request.env.user.id})
            else:
                Member.create({
                    "community_id": community_id,
                    "user_id": uid,
                    "role": "member",
                    "state": "invited",
                    "invited_by": request.env.user.id,
                })
            _notify_user(uid, {"type": "invited", "community_id": community_id})

        _notify_community(community_id, {"type": "members_changed", "community_id": community_id})
        return {"ok": True}

    @http.route("/community_hub/api/community/<int:community_id>/members/kick", type="json", auth="user")
    def kick(self, community_id, userId=None, **kw):
        _ensure_manage(community_id)
        community_id = int(community_id)
        userId = int(userId or 0)
        if not userId:
            raise ValidationError(_("userId is required."))

        Member = request.env["community.hub.member"].sudo()
        m = Member.search([("community_id", "=", community_id), ("user_id", "=", userId)], limit=1)
        if not m:
            return {"ok": True}

        if m.role == "owner":
            raise AccessError(_("Cannot kick owner."))

        # ✅ Kick = UNLINK (đảm bảo không hiện anywhere + không dính selection 'kicked')
        m.unlink()

        _notify_user(userId, {"type": "kicked", "community_id": community_id})
        _notify_community(community_id, {"type": "members_changed", "community_id": community_id})
        return {"ok": True}

    @http.route("/community_hub/api/community/<int:community_id>/members/role", type="json", auth="user")
    def set_role(self, community_id, userId=None, role=None, **kw):
        _ensure_owner(community_id)
        community_id = int(community_id)
        userId = int(userId or 0)
        role = (role or "").strip()

        if role not in ("owner", "admin", "member"):
            raise ValidationError(_("Invalid role."))

        Member = request.env["community.hub.member"].sudo()
        m = Member.search([("community_id", "=", community_id), ("user_id", "=", userId)], limit=1)
        if not m or m.state != "joined":
            raise AccessError(_("User is not a joined member."))

        # prevent removing last owner
        if m.role == "owner" and role != "owner":
            owners = Member.search_count([("community_id", "=", community_id), ("role", "=", "owner"), ("state", "=", "joined")])
            if owners <= 1:
                raise AccessError(_("You must keep at least one owner."))

        m.write({"role": role})
        _notify_community(community_id, {"type": "members_changed", "community_id": community_id})
        return {"ok": True}
