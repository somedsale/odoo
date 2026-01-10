# -*- coding: utf-8 -*-
from odoo import fields, models, api


class CommunityHubChannel(models.Model):
    _name = "community.hub.channel"
    _description = "Community Channel"
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