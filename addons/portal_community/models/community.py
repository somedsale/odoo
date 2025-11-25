# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

# =========================================================
# COMMUNITY
# =========================================================
class PortalCommunity(models.Model):
    _name = "portal.community"
    _description = "Community"
    _order = "name"

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
    is_private = fields.Boolean(string="Private", default=False)

    creator_id = fields.Many2one(
        "res.users",
        string="Creator",
        default=lambda self: self.env.user,
        readonly=True,
    )
    owner_id = fields.Many2one(
        "res.users",
        string="Owner",
        default=lambda self: self.env.user,
        required=True,
    )
    member_ids = fields.One2many(
        "portal.community.member",
        "community_id",
        string="Members",
    )
    channel_ids = fields.One2many(
        "portal.community.channel",
        "community_id",
        string="Channels",
    )

    member_count = fields.Integer(
        string="Members",
        compute="_compute_counts",
    )
    channel_count = fields.Integer(
        string="Channels",
        compute="_compute_counts",
    )

    def _portal_to_dict(self):
        """Dữ liệu để đẩy ra Owl (danh sách communities)."""
        res = []
        for community in self:
            res.append({
                "id": community.id,
                "name": community.name,
                "description": community.description or "",
                "initials": (community.name or " ")[0].upper(),
                "member_count": len(community.member_ids),
                "channels": [c._portal_to_dict() for c in community.channel_ids],
            })
        return res

    @api.depends("member_ids", "channel_ids")
    def _compute_counts(self):
        for rec in self:
            rec.member_count = len(rec.member_ids)
            rec.channel_count = len(rec.channel_ids)

    # ---------- owner helper ----------
    def _is_owner(self, user=None):
        user = user or self.env.user
        self.ensure_one()
        return any(
            m.user_id.id == user.id and m.role == "owner"
            for m in self.member_ids
        )

    def _check_owner(self, user=None):
        user = user or self.env.user
        for rec in self:
            if not rec._is_owner(user):
                raise UserError("Chỉ Owner của cộng đồng mới được phép thao tác này.")

    # ---------- override create: tạo Owner ----------
    @api.model
    def create(self, vals):
        user = self.env.user
        if not vals.get("creator_id"):
            vals["creator_id"] = user.id
        community = super().create(vals)
        # auto add creator as owner nếu chưa có
        self.env["portal.community.member"].create(
            {
                "community_id": community.id,
                "user_id": community.creator_id.id,
                "role": "owner",
            }
        )
        return community

    # ---------- API: mời user vào community ----------
    @api.model
    def invite_member(self, community_id, user_id, role="member"):
        """
        Gọi từ Owl / backend:
          env['portal.community'].invite_member(community_id, user_id, 'member')
        - Chỉ owner của community đó mới mời được
        """
        if role not in ("owner", "member"):
            role = "member"

        community = self.browse(community_id).sudo()
        if not community:
            raise UserError("Community không tồn tại.")
        community._check_owner()

        Member = self.env["portal.community.member"].sudo()
        existing = Member.search(
            [("community_id", "=", community.id), ("user_id", "=", user_id)],
            limit=1,
        )
        if existing:
            existing.role = role  # update role nếu cần
        else:
            Member.create(
                {
                    "community_id": community.id,
                    "user_id": user_id,
                    "role": role,
                }
            )
        return True

    # ---------- API: xóa member khỏi community ----------
    @api.model
    def remove_member(self, member_id):
        """
        Gọi từ Owl / backend:
          env['portal.community'].remove_member(member_id)
        - Chỉ owner của community được phép xóa member
        """
        Member = self.env["portal.community.member"].sudo()
        member = Member.browse(member_id)
        if not member:
            raise UserError("Member không tồn tại.")
        community = member.community_id
        community._check_owner()

        # Không cho xóa chính mình nếu là owner cuối cùng
        if (
            member.role == "owner"
            and member.user_id.id == self.env.uid
            and Member.search_count(
                [
                    ("community_id", "=", community.id),
                    ("role", "=", "owner"),
                    ("id", "!=", member.id),
                ]
            )
            == 0
        ):
            raise UserError(
                "Không thể rời cộng đồng khi bạn là Owner cuối cùng. "
                "Hãy chuyển quyền Owner cho người khác trước."
            )

        member.unlink()
        return True

    def _serialize_member(self, member):
        return {
            "id": member.id,
            "user_id": member.user_id.id,
            "user_name": member.user_id.name,
            "role": member.role,
        }

    def _serialize_channel(self, channel):
        return {
            "id": channel.id,
            "name": channel.name,
            "description": channel.description or "",
            "sequence": channel.sequence,
            "community_id": channel.community_id.id,
            "post_count": channel.post_count,
        }

    def _serialize_comment(self, comment):
        dt = (
            fields.Datetime.context_timestamp(self, comment.create_date)
            if comment.create_date
            else False
        )
        create_human = dt.strftime("%Y-%m-%d %H:%M") if dt else ""
        return {
            "id": comment.id,
            "author_id": comment.author_id.id,
            "author_name": comment.author_id.name,
            "body": html2plaintext(comment.body or "") if comment.body else "",
            "create_human": create_human,
            "attachments": [
                {
                    "id": a.id,
                    "name": a.name,
                    "mimetype": a.mimetype,
                    "url": f"/web/content/{a.id}?download=1",
                }
                for a in comment.attachment_ids
            ],
        }

    def _serialize_post(self, post):
        dt = (
            fields.Datetime.context_timestamp(self, post.create_date)
            if post.create_date
            else False
        )
        create_human = dt.strftime("%Y-%m-%d %H:%M") if dt else ""
        return {
            "id": post.id,
            "community_id": post.community_id.id,
            "channel_id": post.channel_id.id,
            "subject": post.subject or "",
            "body": html2plaintext(post.body or "") if post.body else "",
            "author_id": post.author_id.id,
            "author_name": post.author_id.name,
            "author_initials": (post.author_id.name or "")[:2].upper(),
            "is_announcement": bool(post.is_announcement),
            "is_pinned": bool(post.is_pinned),
            "comment_count": post.comment_count,
            "create_human": create_human,
            "attachments": [
                {
                    "id": a.id,
                    "name": a.name,
                    "mimetype": a.mimetype,
                    "url": f"/web/content/{a.id}?download=1",
                }
                for a in post.attachment_ids
            ],
            "comments": [self._serialize_comment(c) for c in post.comment_ids],
        }

    @api.model
    def get_app_data(self, params=None):
        """Trả về dữ liệu cho Owl app Communities."""
        user = self.env.user
        params = params or {}
        active_community_id = params.get("active_community_id")
        active_channel_id = params.get("active_channel_id")

        # 1. Lấy communities mà user là owner hoặc member
        communities = self.search([
            "|",
            ("owner_id", "=", user.id),
            ("member_ids.user_id", "=", user.id),
        ])

        community_list = []
        for com in communities:
            # channels của community
            channels_payload = []
            for ch in com.channel_ids.sorted("sequence"):
                channels_payload.append({
                    "id": ch.id,
                    "name": ch.name,
                    "description": ch.description or "",
                    "sequence": ch.sequence,
                    "post_count": ch.post_count or 0,
                })

            community_list.append({
                "id": com.id,
                "name": com.name,
                "description": com.description or "",
                "channels": channels_payload,
            })

        # 2. Xác định active community
        if not active_community_id and communities:
            active_community_id = communities[0].id

        active_channel = None
        if active_community_id:
            community = self.browse(active_community_id)
            if not community.exists():
                community = self.env["portal.community"]
            # nếu chưa có channel active thì lấy channel đầu tiên
            if not active_channel_id and community.channel_ids:
                active_channel = community.channel_ids.sorted("sequence")[0]
                active_channel_id = active_channel.id
            elif active_channel_id:
                active_channel = self.env["portal.community.channel"].browse(active_channel_id)
        else:
            community = self.env["portal.community"]
            active_channel = self.env["portal.community.channel"]

        # 3. Lấy posts cho active_channel
        posts_payload = []
        if active_channel and active_channel.exists():
            Post = self.env["portal.community.post"]
            posts = Post.search(
                [("channel_id", "=", active_channel.id)],
                order="create_date desc",
                limit=30,
            )
            for post in posts:
                # comments
                comments_payload = []
                for c in post.comment_ids.sorted("create_date"):
                    comments_payload.append({
                        "id": c.id,
                        "author_name": c.author_id.name or "",
                        "author_initials": (c.author_id.name or " ")[:2].upper(),
                        "body": c.body or "",
                        "create_date": fields.Datetime.to_string(c.create_date),
                        "create_date_human": fields.Datetime.to_string(c.create_date),
                    })

                # attachments
                attach_payload = []
                for att in post.attachment_ids:
                    attach_payload.append({
                        "id": att.id,
                        "name": att.name,
                        "mimetype": att.mimetype,
                        "url": "/web/content/%s?download=1" % att.id,
                    })

                posts_payload.append({
                    "id": post.id,
                    "community_id": post.community_id.id,
                    "channel_id": post.channel_id.id,
                    "subject": post.subject or "",
                    "body": post.body or "",
                    "author_name": post.author_id.name or "",
                    "author_initials": (post.author_id.name or " ")[:2].upper(),
                    "create_date": fields.Datetime.to_string(post.create_date),
                    "create_date_human": fields.Datetime.to_string(post.create_date),
                    "comment_count": len(post.comment_ids),
                    "comments": comments_payload,
                    "attachments": attach_payload,
                })

        return {
            "communities": community_list,
            "active_community_id": active_community_id,
            "active_channel_id": active_channel_id,
            "posts": posts_payload,
        }

# =========================================================
# COMMUNITY MEMBER
# =========================================================
class PortalCommunityMember(models.Model):
    _name = "portal.community.member"
    _description = "Community Member"
    _order = "community_id, role, user_id"

    community_id = fields.Many2one(
        "portal.community",
        string="Community",
        required=True,
        ondelete="cascade",
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        ondelete="cascade",
    )
    role = fields.Selection(
        [("owner", "Owner"), ("member", "Member")],
        string="Role",
        required=True,
        default="member",
    )

    _sql_constraints = [
        (
            "community_user_unique",
            "unique(community_id, user_id)",
            "Một người dùng chỉ được xuất hiện một lần trong 1 community.",
        )
    ]


# =========================================================
# CHANNEL
# =========================================================
class PortalCommunityChannel(models.Model):
    _name = "portal.community.channel"
    _description = "Community Channel"
    _order = "sequence, name"

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
    sequence = fields.Integer(default=10)

    community_id = fields.Many2one(
        "portal.community",
        string="Community",
        required=True,
        ondelete="cascade",
    )

    post_ids = fields.One2many(
        "portal.community.post",
        "channel_id",
        string="Posts",
    )

    post_count = fields.Integer(
        string="Posts",
        compute="_compute_post_count",
    )

    @api.depends("post_ids")
    def _compute_post_count(self):
        for rec in self:
            rec.post_count = len(rec.post_ids)

    def _portal_to_dict(self):
        res = []
        for channel in self:
            res.append({
                "id": channel.id,
                "name": channel.name,
                "description": channel.description or "",
                "post_count": channel.post_count,
            })
        return res


# =========================================================
# POST
# =========================================================
class PortalCommunityPost(models.Model):
    _name = "portal.community.post"
    _description = "Community Post"
    _order = "is_pinned desc, create_date desc"

    community_id = fields.Many2one(
        "portal.community",
        string="Community",
        compute="_compute_community",
        store=True,
        readonly=True,
    )

    channel_id = fields.Many2one(
        "portal.community.channel",
        string="Channel",
        required=True,
        ondelete="cascade",
    )

    subject = fields.Char(string="Subject")
    body = fields.Html(
        string="Body",
        sanitize=True,
        sanitize_attributes=False,
        sanitize_style=True,
    )

    author_id = fields.Many2one(
        "res.users",
        string="Author",
        default=lambda self: self.env.user,
        readonly=True,
    )

    is_announcement = fields.Boolean("Announcement", default=False)
    is_pinned = fields.Boolean("Pinned", default=False)

    comment_ids = fields.One2many(
        "portal.community.comment",
        "post_id",
        string="Comments",
    )

    comment_count = fields.Integer(
        string="Comments",
        compute="_compute_comment_count",
    )

    attachment_ids = fields.One2many(
        "ir.attachment",
        "res_id",
        string="Attachments",
        domain=[("res_model", "=", "portal.community.post")],
    )

    @api.depends("channel_id")
    def _compute_community(self):
        for rec in self:
            rec.community_id = rec.channel_id.community_id

    @api.depends("comment_ids")
    def _compute_comment_count(self):
        for rec in self:
            rec.comment_count = len(rec.comment_ids)

    # dùng cho Owl app nếu muốn tạo post từ JS
    @api.model
    def create_from_app(self, channel_id, subject, body, attachments=None, is_announcement=False):
        """
        attachments: list[{name, data(base64), mimetype}]
        """
        if not channel_id:
            raise UserError("channel_id là bắt buộc")

        vals = {
            "channel_id": channel_id,
            "subject": subject or "",
            "body": body or "",
            "is_announcement": bool(is_announcement),
        }
        post = self.create(vals)

        Attachment = self.env["ir.attachment"].sudo()
        for att in attachments or []:
            if not att.get("data"):
                continue
            Attachment.create(
                {
                    "name": att.get("name") or "File",
                    "datas": att["data"],
                    "mimetype": att.get("mimetype"),
                    "res_model": "portal.community.post",
                    "res_id": post.id,
                }
            )
        return post.id

    def _portal_datetime_human(self, dt):
        if not dt:
            return ""
        # có thể custom thêm "hôm qua", "2 giờ trước"...
        return fields.Datetime.to_string(dt)

    def _portal_to_dict(self):
        self.ensure_one()
        return {
            "id": self.id,
            "subject": self.subject or "",
            "body": self.body or "",
            "author_name": self.author_id.name or "",
            "author_initials": (self.author_id.name or " ")[:2].upper(),
            "create_date": fields.Datetime.to_string(self.create_date),
            "create_date_human": self._portal_datetime_human(self.create_date),
            "attachments": [
                {
                    "id": att.id,
                    "name": att.name,
                    "url": "/web/content/%s?download=1" % att.id,
                }
                for att in self.attachment_ids
            ],
            "comments": [c._portal_to_dict() for c in self.comment_ids],
        }


    # ========= API cho Owl ===========

    @api.model
    def create_from_portal(self, vals):
        """
        Được gọi từ Owl khi bấm Post.
        JS gọi: this.orm.call('portal.community.post', 'create_from_portal', [vals])
        """
        community_id = vals.get("community_id")
        channel_id = vals.get("channel_id")
        if not community_id or not channel_id:
            raise UserError(_("Missing community or channel"))

        subject = (vals.get("subject") or "").trim()
        body = (vals.get("body") or "").strip()

        if not body and not subject:
            raise UserError(_("Empty post"))

        # convert text -> HTML đơn giản nếu muốn:
        body_html = vals.get("body_html")
        if not body_html and body:
            body_html = "<p>%s</p>" % body.replace("\n", "<br/>")

        post = self.create({
            "community_id": community_id,
            "channel_id": channel_id,
            "subject": subject,
            "body": body_html or body or "",
            "author_id": self.env.user.id,   # user, không phải partner
        })
        return post._portal_to_dict()


    @api.model
    def get_posts_for_channel(self, channel_id):
        channel = self.env["portal.community.channel"].browse(channel_id).exists()
        if not channel:
            return []
        posts = self.search(
            [("channel_id", "=", channel_id)],
            order="create_date desc",
            limit=50,
        )
        return [p._portal_to_dict() for p in posts]


# =========================================================
# COMMENT
# =========================================================
class PortalCommunityComment(models.Model):
    _name = "portal.community.comment"
    _description = "Community Comment"
    _order = "create_date"

    post_id = fields.Many2one(
        "portal.community.post",
        string="Post",
        required=True,
        ondelete="cascade",
    )

    community_id = fields.Many2one(
        related="post_id.community_id",
        store=True,
        readonly=True,
    )

    body = fields.Html(
        string="Body",
        sanitize=True,
        sanitize_attributes=False,
        sanitize_style=True,
    )

    author_id = fields.Many2one(
        "res.users",
        string="Author",
        default=lambda self: self.env.user,
        readonly=True,
    )

    attachment_ids = fields.One2many(
        "ir.attachment",
        "res_id",
        string="Attachments",
        domain=[("res_model", "=", "portal.community.comment")],
    )

    @api.model
    def create_from_app(self, post_id, body, attachments=None):
        """
        attachments: list[{name, data(base64), mimetype}]
        """
        if not post_id:
            raise UserError("post_id là bắt buộc")

        vals = {
            "post_id": post_id,
            "body": body or "",
        }
        comment = self.create(vals)

        Attachment = self.env["ir.attachment"].sudo()
        for att in attachments or []:
            if not att.get("data"):
                continue
            Attachment.create(
                {
                    "name": att.get("name") or "File",
                    "datas": att["data"],
                    "mimetype": att.get("mimetype"),
                    "res_model": "portal.community.comment",
                    "res_id": comment.id,
                }
            )
        return comment.id

    def _portal_to_dict(self):
        self.ensure_one()
        return {
            "id": self.id,
            "body": self.body or "",
            "author_name": self.author_id.name or "",
            "author_initials": (self.author_id.name or " ")[:2].upper(),
            "create_date": fields.Datetime.to_string(self.create_date),
            "create_date_human": fields.Datetime.to_string(self.create_date),
        }

    @api.model
    def create_from_portal(self, vals):
        """
        JS sẽ gọi khi user comment.
        """
        post_id = vals.get("post_id")
        body = (vals.get("body") or "").strip()
        if not post_id or not body:
            raise UserError(_("Missing post or body"))

        body_html = "<p>%s</p>" % body.replace("\n", "<br/>")

        comment = self.create({
            "post_id": post_id,
            "body": body_html,
            "author_id": self.env.user.id,
        })
        return comment._portal_to_dict()
