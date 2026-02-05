# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CommunityHubPost(models.Model):
    _name = "community.hub.post"
    _description = "Community Post"
    _inherit = ["mail.thread", "mail.activity.mixin"]  # nếu post chưa inherit
    _order = "create_date desc"

    community_id = fields.Many2one("community.hub", required=True, ondelete="cascade", index=True)
    channel_id = fields.Many2one("community.hub.channel", required=True, ondelete="cascade", index=True)
    author_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True)

    body_html = fields.Html(required=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "community_post_attachment_rel",
        "post_id",
        "attachment_id",
        string="Attachments",
    )

    # inverse_name MUST exist on comodel
    comment_ids = fields.One2many("community.hub.comment", "post_id", string="Comments")
    reaction_ids = fields.One2many("community.hub.reaction", "post_id", string="Reactions")

    def _check_member(self):
        for rec in self:
            self.env["community.hub.member"].ensure_joined(rec.community_id.id)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._check_member()
            self.env["community.hub.member"]._bus_broadcast(rec.community_id.id, {
                "type": "post_created",
                "community_id": rec.community_id.id,
                "post_id": rec.id,
            })
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            self.env["community.hub.member"]._bus_broadcast(rec.community_id.id, {
                "type": "post_updated",
                "community_id": rec.community_id.id,
                "post_id": rec.id,
            })
        return res

    def unlink(self):
        payloads = [{"community_id": r.community_id.id, "post_id": r.id} for r in self]
        res = super().unlink()
        for p in payloads:
            self.env["community.hub.member"]._bus_broadcast(p["community_id"], {"type": "post_deleted", **p})
        return res
    def get_access_action(self, access_uid=None):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "community_hub.client_action",
            "name": "Community Hub",
            "params": {
                "community_id": self.community_id.id,
                "channel_id": self.channel_id.id,
                "post_id": self.id,
                "tab": "posts",
            },
        }
    def _hub_act_url(self, community_id=None, channel_id=None, post_id=None, tab="posts"):
        action = self.env.ref("community_hub.action_community_hub_client", raise_if_not_found=False)
        menu = self.env.ref("community_hub.menu_community_hub_root", raise_if_not_found=False)

        parts = []
        if action:
            parts.append(f"action={action.id}")
        if menu:
            parts.append(f"menu_id={menu.id}")

        if community_id:
            parts.append(f"community_id={int(community_id)}")
        if channel_id:
            parts.append(f"channel_id={int(channel_id)}")
        if post_id:
            parts.append(f"post_id={int(post_id)}")
        if tab:
            parts.append(f"tab={tab}")

        url = "/web#" + "&".join(parts) if parts else "/web"
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def get_formview_action(self, access_uid=None):
        self.ensure_one()
        return self._hub_act_url(
            community_id=getattr(self, "community_id", False) and self.community_id.id or None,
            channel_id=getattr(self, "channel_id", False) and self.channel_id.id or None,
            post_id=self.id,
            tab="posts",
        )