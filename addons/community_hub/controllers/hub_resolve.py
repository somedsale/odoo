# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class CommunityHubResolveController(http.Controller):

    @http.route("/community_hub/action_menu_ids", type="json", auth="user")
    def action_menu_ids(self):
        action = request.env.ref("community_hub.action_community_hub_client", raise_if_not_found=False)
        menu = request.env.ref("community_hub.menu_community_hub_root", raise_if_not_found=False)
        return {
            "action_id": action.id if action else False,
            "menu_id": menu.id if menu else False,
        }

    @http.route("/community_hub/resolve_deeplink", type="json", auth="user")
    def resolve_deeplink(self, model=None, res_id=None):
        model = (model or "").strip()
        rid = int(res_id or 0)
        env = request.env

        out = {"community_id": 0, "channel_id": 0, "post_id": 0}

        if model == "community.hub.post":
            p = env[model].sudo().browse(rid).exists()
            if p:
                out.update({
                    "community_id": p.community_id.id if p.community_id else 0,
                    "channel_id": p.channel_id.id if p.channel_id else 0,
                    "post_id": p.id,
                })
        elif model == "community.hub.channel":
            ch = env[model].sudo().browse(rid).exists()
            if ch:
                out.update({
                    "community_id": ch.community_id.id if ch.community_id else 0,
                    "channel_id": ch.id,
                    "post_id": 0,
                })
        elif model == "community.hub":
            c = env[model].sudo().browse(rid).exists()
            if c:
                out.update({
                    "community_id": c.id,
                    "channel_id": 0,
                    "post_id": 0,
                })

        return out
