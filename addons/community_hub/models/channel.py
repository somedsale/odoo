# -*- coding: utf-8 -*-
from odoo import fields, models, api


class CommunityHubChannel(models.Model):
    _name = "community.hub.channel"
    _description = "Community Channel"
    _inherit = ["mail.thread", "mail.activity.mixin"]  # nếu bạn chưa inherit mail.thread
    _order = "sequence, id"
    community_id = fields.Many2one("community.hub", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)

    post_ids = fields.One2many("community.hub.post", "channel_id", string="Posts")
    name_key = fields.Char(compute="_compute_name_key", store=True, index=True)

    @api.depends("name")
    def _compute_name_key(self):
        for r in self:
            r.name_key = (r.name or "").strip().lower()

    _sql_constraints = [
        ("uniq_channel_per_community", "unique(community_id, name_key)", "Channel name already exists in this community."),
    ]
    def get_access_action(self, access_uid=None):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "community_hub.client_action",
            "name": "Community Hub",
            "params": {
                "community_id": self.community_id.id,
                "channel_id": self.id,
                "tab": "posts",
            },
        }
    def get_formview_action(self, access_uid=None):
        self.ensure_one()
        # dùng helper từ post nếu bạn để chung mixin thì tốt hơn,
        # còn không thì copy _hub_act_url sang đây y hệt.
        action = self.env.ref("community_hub.action_community_hub_client", raise_if_not_found=False)
        menu = self.env.ref("community_hub.menu_community_hub_root", raise_if_not_found=False)

        parts = []
        if action:
            parts.append(f"action={action.id}")
        if menu:
            parts.append(f"menu_id={menu.id}")
        if self.community_id:
            parts.append(f"community_id={self.community_id.id}")
        parts.append(f"channel_id={self.id}")
        parts.append("tab=posts")

        return {"type": "ir.actions.act_url", "url": "/web#" + "&".join(parts), "target": "self"}