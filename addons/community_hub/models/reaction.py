# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CommunityHubReaction(models.Model):
    _name = "community.hub.reaction"
    _description = "Community Reaction"
    _order = "id desc"
    _sql_constraints = [
        ("uniq_reaction", "unique(post_id, comment_id, user_id, emoji)", "Reaction already exists."),
    ]

    # Inverse for post.reaction_ids
    post_id = fields.Many2one("community.hub.post", ondelete="cascade", index=True)
    comment_id = fields.Many2one("community.hub.comment", ondelete="cascade", index=True)

    community_id = fields.Many2one("community.hub", required=True, ondelete="cascade", index=True)
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True)
    emoji = fields.Char(required=True)

    @api.constrains("post_id", "comment_id")
    def _check_target(self):
        for rec in self:
            if bool(rec.post_id) == bool(rec.comment_id):
                raise ValidationError(_("Reaction must target either a post or a comment."))

    @api.model
    def toggle(self, community_id, post_id=None, comment_id=None, emoji="👍"):
        self.env["community.hub.member"].ensure_joined(community_id)

        domain = [
            ("community_id", "=", community_id),
            ("user_id", "=", self.env.user.id),
            ("emoji", "=", emoji),
        ]
        if post_id:
            domain += [("post_id", "=", post_id), ("comment_id", "=", False)]
        else:
            domain += [("comment_id", "=", comment_id), ("post_id", "=", False)]

        existing = self.search(domain, limit=1)
        if existing:
            existing.unlink()
            action = "removed"
        else:
            self.create({
                "community_id": community_id,
                "post_id": post_id,
                "comment_id": comment_id,
                "emoji": emoji,
            })
            action = "added"

        self.env["community.hub.member"]._bus_broadcast(community_id, {
            "type": "reaction_updated",
            "community_id": community_id,
            "post_id": post_id,
            "comment_id": comment_id,
            "emoji": emoji,
            "action": action,
        })
        return {"ok": True, "action": action}
