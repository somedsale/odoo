# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class CommunityInvite(models.Model):
    _name = "community.invite"
    _description = "Community Invitation"
    _order = "create_date desc"

    community_id = fields.Many2one("community.community", required=True, ondelete="cascade", index=True)
    invited_user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    invited_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True)
    state = fields.Selection(
        [("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined")],
        default="pending",
        required=True,
        index=True,
    )

    _sql_constraints = [
        ("uniq_pending_invite",
         "unique(community_id, invited_user_id, state)",
         "Invitation already exists."),
    ]

    def _check_inviter_member(self):
        self.ensure_one()
        self.community_id._check_is_member()

    @api.model
    def owl_create_invite(self, community_id, invited_user_id):
        community = self.env["community.community"].browse(int(community_id)).exists()
        if not community:
            raise UserError(_("Community not found."))

        # inviter must be member/owner
        community._check_is_member()

        # if already member -> no need invite
        if int(invited_user_id) in community.member_user_ids.ids:
            return {"ok": True, "already_member": True}

        inv = self.create({
            "community_id": community.id,
            "invited_user_id": int(invited_user_id),
        })

        # realtime notify invited user
        bus = self.env["community_hub.bus_utils"]
        bus.send_to_partners([inv.invited_user_id.partner_id.id], {
            "event": "invite_changed",
        })

        return {"ok": True, "id": inv.id}

    def action_accept(self):
        for inv in self:
            if inv.invited_user_id != self.env.user:
                raise AccessError(_("Not your invitation."))
            if inv.state != "pending":
                continue
            inv.community_id.write({"member_user_ids": [(4, self.env.user.id)]})
            inv.state = "accepted"

            bus = self.env["community_hub.bus_utils"]
            partner_ids = bus.partners_of_community(inv.community_id)
            bus.send_to_partners(partner_ids, {"event": "member_changed", "community_id": inv.community_id.id})
            bus.send_to_partners([self.env.user.partner_id.id], {"event": "invite_changed"})

    def action_decline(self):
        for inv in self:
            if inv.invited_user_id != self.env.user:
                raise AccessError(_("Not your invitation."))
            if inv.state != "pending":
                continue
            inv.state = "declined"
            bus = self.env["community_hub.bus_utils"]
            bus.send_to_partners([self.env.user.partner_id.id], {"event": "invite_changed"})
