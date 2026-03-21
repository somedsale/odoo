# -*- coding: utf-8 -*-
from werkzeug.urls import url_encode

from odoo import http
from odoo.http import request


class ProjectWorkAssignmentNotifyController(http.Controller):

    def _safe_int(self, value):
        try:
            return int(value)
        except Exception:
            return False

    def _mark_notifications_as_read(self, model=None, record_id=None):
        user = request.env.user
        partner = user.partner_id
        if not model or not record_id or not partner:
            return

        try:
            messages = request.env["mail.message"].sudo().search([
                ("model", "=", model),
                ("res_id", "=", int(record_id)),
            ])
            if not messages:
                return

            notifications = request.env["mail.notification"].sudo().search([
                ("mail_message_id", "in", messages.ids),
                ("res_partner_id", "=", partner.id),
                ("is_read", "=", False),
            ])
            if notifications:
                notifications.write({"is_read": True})
        except Exception:
            pass

    def _redirect_web_hash(self, params):
        return request.redirect("/web#%s" % url_encode(params))

    def _redirect_to_client_action(self, action_xmlid, project_id=None):
        action = request.env.ref(action_xmlid, raise_if_not_found=False)
        if not action:
            return request.redirect("/web")

        params = {
            "action": action.id,
            "model": "project.project",
        }

        project_id_int = self._safe_int(project_id)
        if project_id_int:
            params["id"] = project_id_int
            params["active_id"] = project_id_int

        return self._redirect_web_hash(params)

    @http.route(
        "/project_work_assignment_notify/open_message_report",
        type="http",
        auth="user",
        website=False,
    )
    def open_message_report(
        self,
        model=None,
        res_id=None,
        id=None,
        action_id=None,
        view_id=None,
        menu_id=None,
        **kwargs
    ):
        record_id = res_id or id
        record_id_int = self._safe_int(record_id)

        if model and record_id_int:
            self._mark_notifications_as_read(model=model, record_id=record_id_int)

        params = {}

        action_id_int = self._safe_int(action_id)
        if action_id_int:
            params["action"] = action_id_int

        if model:
            params["model"] = model

        if record_id_int:
            params["id"] = record_id_int
            params["view_type"] = "form"
        else:
            params["view_type"] = "list"

        view_id_int = self._safe_int(view_id)
        if view_id_int and record_id_int:
            params["view_id"] = view_id_int

        menu_id_int = self._safe_int(menu_id)
        if menu_id_int:
            params["menu_id"] = menu_id_int

        return self._redirect_web_hash(params)

    @http.route(
        "/project_work_assignment_notify/open_my_assignment_report",
        type="http",
        auth="user",
        website=False,
    )
    def open_my_assignment_report(self, project_id=None, **kwargs):
        project_id_int = self._safe_int(project_id)
        if project_id_int:
            self._mark_notifications_as_read(
                model="project.project",
                record_id=project_id_int,
            )
        return self._redirect_to_client_action(
            "project_work_from_so.action_open_my_assignment_report_client",
            project_id=project_id_int,
        )

    @http.route(
        "/project_work_assignment_notify/open_my_acceptance_report",
        type="http",
        auth="user",
        website=False,
    )
    def open_my_acceptance_report(self, project_id=None, **kwargs):
        project_id_int = self._safe_int(project_id)
        if project_id_int:
            self._mark_notifications_as_read(
                model="project.project",
                record_id=project_id_int,
            )
        return self._redirect_to_client_action(
            "project_work_acceptance_report.action_open_my_acceptance_report_client",
            project_id=project_id_int,
        )

    @http.route(
        "/project_work_assignment_notify/open_my_claim_report",
        type="http",
        auth="user",
        website=False,
    )
    def open_my_claim_report(self, project_id=None, **kwargs):
        project_id_int = self._safe_int(project_id)
        if project_id_int:
            self._mark_notifications_as_read(
                model="project.project",
                record_id=project_id_int,
            )
        return self._redirect_to_client_action(
            "project_work_claim_report.action_open_my_claim_report_client",
            project_id=project_id_int,
        )
    @http.route(
        "/project_work_assignment_notify/open_my_finalization_report",
        type="http",
        auth="user",
        website=False,
    )
    def open_my_finalization_report(self, project_id=None, **kwargs):
        project_id_int = self._safe_int(project_id)
        if project_id_int:
            self._mark_notifications_as_read(
                model="project.project",
                record_id=project_id_int,
            )

        return self._redirect_to_client_action(
            "project_work_finalization_report.action_open_my_finalization_report_client",
            project_id=project_id_int,
        )