# -*- coding: utf-8 -*-
from werkzeug.urls import url_encode

from odoo import http
from odoo.http import request


class ProjectWorkAssignmentNotifyController(http.Controller):

    @http.route(
        "/project_work_assignment_notify/open_message_report",
        type="http",
        auth="user",
        website=False,
    )
    def open_message_report(self, model=None, res_id=None, action_id=None, view_id=None, **kwargs):
        user = request.env.user
        partner = user.partner_id

        # Đánh dấu đã đọc các notification của user hiện tại
        # trên record đang được mở
        if model and res_id:
            try:
                messages = request.env["mail.message"].sudo().search([
                    ("model", "=", model),
                    ("res_id", "=", int(res_id)),
                ])
                if messages:
                    notifications = request.env["mail.notification"].sudo().search([
                        ("mail_message_id", "in", messages.ids),
                        ("res_partner_id", "=", partner.id),
                        ("is_read", "=", False),
                    ])
                    if notifications:
                        notifications.write({"is_read": True})
            except Exception:
                pass

        params = {}
        if action_id:
            params["action"] = int(action_id)
        if model:
            params["model"] = model

        if res_id:
            params["id"] = int(res_id)
            params["view_type"] = "form"
        else:
            params["view_type"] = "list"

        if view_id and res_id:
            params["view_id"] = int(view_id)

        return request.redirect("/web#%s" % url_encode(params))