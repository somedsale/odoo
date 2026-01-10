# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class CommunityHubMember(models.Model):
    _name = "community.hub.member"
    _description = "Community Member"
    _order = "id desc"
    _sql_constraints = [
        ("uniq_member", "unique(community_id, user_id)", "User already exists in this community."),
    ]

    community_id = fields.Many2one("community.hub", required=True, ondelete="cascade", index=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    role = fields.Selection([("owner", "Owner"), ("admin", "Admin"), ("member", "Member")], default="member", required=True)
    state = fields.Selection([
        ("invited", "Invited"),
        ("joined", "Joined"),
        ("kicked", "Kicked"),     # ✅ thêm dòng này
    ], default="invited", required=True, tracking=True)
    invited_by = fields.Many2one("res.users", default=lambda self: self.env.user)

    @api.model
    def ensure_joined(self, community_id):
        m = self.search([
            ("community_id", "=", community_id),
            ("user_id", "=", self.env.user.id),
            ("state", "=", "joined")
        ], limit=1)
        if not m:
            raise AccessError(_("You are not a member of this community."))
        return True

    def action_accept(self):
        for rec in self:
            if rec.user_id != self.env.user:
                raise AccessError(_("Only invited user can accept."))
            rec.state = "joined"
            rec._bus_broadcast(rec.community_id.id, {
                "type": "member_updated",
                "community_id": rec.community_id.id,
                "user_id": rec.user_id.id,
            })

    def action_kick(self):
        for rec in self:
            if rec.community_id.owner_id != self.env.user:
                raise AccessError(_("Only owner can kick members."))
            if rec.role == "owner":
                raise ValidationError(_("Cannot kick owner."))
            uid = rec.user_id.id
            cid = rec.community_id.id
            rec.unlink()
            self._bus_broadcast(cid, {"type": "member_kicked", "community_id": cid, "user_id": uid})

    @api.model
    def invite_users(self, community_id, user_ids):
        community = self.env["community.hub"].browse(community_id)
        if community.owner_id != self.env.user:
            raise AccessError(_("Only owner can invite."))

        created = []
        for uid in user_ids:
            if self.search([("community_id", "=", community_id), ("user_id", "=", uid)], limit=1):
                continue
            created.append(self.create({
                "community_id": community_id,
                "user_id": uid,
                "role": "member",
                "state": "invited",
                "invited_by": self.env.user.id,
            }).id)

        self._bus_broadcast(community_id, {"type": "member_invited", "community_id": community_id})
        for uid in user_ids:
            self._bus_notify_user(uid, {"type": "invited", "community_id": community_id})
        return created

    # ===== BUS HELPERS =====
    @api.model
    def _bus_broadcast(self, community_id, payload):
        dbname = self.env.cr.dbname
        channel = ("community_hub", int(community_id))  # ✅ match JS: bus.addChannel("community_hub", id)
        self.env["bus.bus"]._sendone(dbname, channel, payload)

    @api.model
    def _bus_notify_user(self, user_id, payload):
        dbname = self.env.cr.dbname
        channel = ("community_hub.user", int(user_id))  # ✅ match JS: bus.addChannel("community_hub.user", id)
        self.env["bus.bus"]._sendone(dbname, channel, payload)
