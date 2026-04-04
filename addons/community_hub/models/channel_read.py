# -*- coding: utf-8 -*-
from odoo import models, fields

class CommunityHubChannelRead(models.Model):
    _name = "community.hub.channel.read"
    _description = "Community Hub Channel Read State"
    _rec_name = "channel_id"
    _order = "write_date desc"

    community_id = fields.Many2one("community.hub", required=True, index=True, ondelete="cascade")
    channel_id = fields.Many2one("community.hub.channel", required=True, index=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade")

    last_read_post_id = fields.Many2one("community.hub.post", index=True)
    last_read_at = fields.Datetime(default=fields.Datetime.now)

    _sql_constraints = [
        ("uniq_user_channel", "unique(channel_id, user_id)", "Read state already exists for this user/channel."),
    ]
