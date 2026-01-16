# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CommunityHubComment(models.Model):
    _name = "community.hub.comment"
    _description = "Community Comment"
    _order = "create_date asc"

    # MUST be exactly post_id to match One2many inverse_name
    post_id = fields.Many2one("community.hub.post", required=True, ondelete="cascade", index=True)

    community_id = fields.Many2one(related="post_id.community_id", store=True, index=True)
    author_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True)

    body_html = fields.Html(required=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "community_comment_attachment_rel",
        "comment_id",
        "attachment_id",
        string="Attachments",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            self.env["community.hub.member"].ensure_joined(rec.community_id.id)
            self.env["community.hub.member"]._bus_broadcast(rec.community_id.id, {
                "type": "comment_created",
                "community_id": rec.community_id.id,
                "post_id": rec.post_id.id,
                "comment_id": rec.id,
            })
        return records
