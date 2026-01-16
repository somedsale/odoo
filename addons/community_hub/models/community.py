# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class CommunityHub(models.Model):
    _name = "community.hub"
    _description = "Community Hub"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(required=True, tracking=True)
    description_html = fields.Html(string="Description")

    owner_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, tracking=True)
    is_public = fields.Boolean(default=False, tracking=True)
    join_policy = fields.Selection(
        [("invite", "Invite Only"), ("request", "Request to Join"), ("open", "Open")],
        default="invite",
        required=True,
        tracking=True,
    )

    member_ids = fields.One2many("community.hub.member", "community_id", string="Members")
    channel_ids = fields.One2many("community.hub.channel", "community_id", string="Channels")

    def _ensure_owner(self):
        for rec in self:
            if rec.owner_id != self.env.user:
                raise AccessError(_("Only owner can do this action."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        Member = self.env["community.hub.member"].sudo()
        Channel = self.env["community.hub.channel"].sudo()

        for rec in records:
            # Owner auto-joined
            Member.create({
                "community_id": rec.id,
                "user_id": rec.owner_id.id,
                "role": "owner",
                "state": "joined",
                "invited_by": rec.owner_id.id,
            })
            # Default channel
            Channel.create({
                "community_id": rec.id,
                "name": _("General"),
                "sequence": 10,
            })
        return records

    def action_add_channel(self, name):
        self._ensure_owner()
        return self.env["community.hub.channel"].create({
            "community_id": self.id,
            "name": name,
        })
