# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import api, models, _
from odoo.tools import html_escape


class ProjectWorkItem(models.Model):
    _inherit = "project.work.item"

    # =========================================================
    # CONFIG
    # =========================================================
    def _assignment_notify_role_map(self):
        return {
            "assigned_user_id": {
                "label": _("báo cáo sản lượng"),
                "action_xmlid": "project_work_from_so.action_my_assignment_report",
                "form_view_xmlid": "project_work_from_so.view_my_assignment_report_form",
                "assignment_user_field": "user_id",
            },
            "claim_user_id": {
                "label": _("báo cáo thanh / quyết toán"),
                "action_xmlid": "project_work_claim_report.action_my_assignment_claim_report",
                "form_view_xmlid": "project_work_claim_report.view_my_assignment_claim_report_form",
                "assignment_user_field": "claim_user_id",
            },
            "acceptance_user_id": {
                "label": _("báo cáo nghiệm thu"),
                "action_xmlid": "project_work_acceptance_report.action_my_assignment_acceptance_report",
                "form_view_xmlid": "project_work_acceptance_report.view_my_assignment_acceptance_report_form",
                "assignment_user_field": "acceptance_user_id",
            },
        }

    def _assignment_notify_tracked_fields(self):
        return ["claim_user_id", "acceptance_user_id"]

    # =========================================================
    # OLD VALUES
    # =========================================================
    def _assignment_notify_prepare_old_map(self):
        data = {}
        for rec in self:
            data[rec.id] = {
                "assigned_user_id": rec.assigned_user_id.id if "assigned_user_id" in rec._fields and rec.assigned_user_id else False,
                "claim_user_id": rec.claim_user_id.id if "claim_user_id" in rec._fields and rec.claim_user_id else False,
                "acceptance_user_id": rec.acceptance_user_id.id if "acceptance_user_id" in rec._fields and rec.acceptance_user_id else False,
            }
        return data

    # =========================================================
    # LINK FIELD project.work.assignment -> project.work.item
    # =========================================================
    def _get_assignment_link_field_candidates(self):
        return [
            "work_item_id",
            "project_work_item_id",
            "item_id",
        ]

    # =========================================================
    # FIND RELATED ASSIGNMENT RECORD
    # =========================================================
    def _find_related_assignment_record(self, field_name, target_user):
        self.ensure_one()

        Assignment = self.env["project.work.assignment"]
        conf = self._assignment_notify_role_map().get(field_name, {})
        user_field = conf.get("assignment_user_field")

        if not user_field or user_field not in Assignment._fields:
            return Assignment.browse()

        link_fields = [
            fname for fname in self._get_assignment_link_field_candidates()
            if fname in Assignment._fields
        ]
        if not link_fields:
            return Assignment.browse()

        base_domain = [(user_field, "=", target_user.id)]
        if "active" in Assignment._fields:
            base_domain.append(("active", "=", True))

        for link_field in link_fields:
            domain = list(base_domain)
            domain.append((link_field, "=", self.id))
            rec = Assignment.search(domain, limit=1, order="id desc")
            if rec:
                return rec

        return Assignment.browse()

    # =========================================================
    # ACTION / URL
    # =========================================================
    def _get_assignment_fallback_action(self, field_name):
        self.ensure_one()

        conf = self._assignment_notify_role_map().get(field_name, {})
        action_xmlid = conf.get("action_xmlid")
        if not action_xmlid:
            return {}

        action = self.env.ref(action_xmlid, raise_if_not_found=False)
        if not action:
            return {}

        action_dict = action.read()[0]
        ctx = dict(self.env.context or {})
        ctx.update({
            "from_assignment_notification": 1,
            "default_project_id": self.project_id.id if getattr(self, "project_id", False) else False,
            "default_work_item_id": self.id,
            "active_model": "project.work.item",
            "active_id": self.id,
            "active_ids": [self.id],
        })
        action_dict["context"] = ctx
        return action_dict

    def _get_assignment_next_action(self, field_name, target_user):
        self.ensure_one()

        assignment_rec = self._find_related_assignment_record(field_name, target_user)
        if assignment_rec:
            conf = self._assignment_notify_role_map().get(field_name, {})
            form_view_xmlid = conf.get("form_view_xmlid")
            form_view = self.env.ref(form_view_xmlid, raise_if_not_found=False) if form_view_xmlid else False

            return {
                "type": "ir.actions.act_window",
                "name": assignment_rec.display_name or _("Chi tiết báo cáo"),
                "res_model": "project.work.assignment",
                "res_id": assignment_rec.id,
                "view_mode": "form",
                "view_id": form_view.id if form_view else False,
                "views": [[form_view.id, "form"]] if form_view else [[False, "form"]],
                "target": "current",
                "context": {
                    "from_assignment_notification": 1,
                    "active_model": "project.work.assignment",
                    "active_id": assignment_rec.id,
                    "active_ids": [assignment_rec.id],
                    "default_project_id": self.project_id.id if getattr(self, "project_id", False) else False,
                    "default_work_item_id": self.id,
                },
            }

        return self._get_assignment_fallback_action(field_name)
    def _get_assignment_record_url(self, field_name, assignment_rec):
        self.ensure_one()
        if not assignment_rec:
            return "#"

        conf = self._assignment_notify_role_map().get(field_name, {})
        action_xmlid = conf.get("action_xmlid")
        form_view_xmlid = conf.get("form_view_xmlid")

        action = self.env.ref(action_xmlid, raise_if_not_found=False) if action_xmlid else False
        form_view = self.env.ref(form_view_xmlid, raise_if_not_found=False) if form_view_xmlid else False

        params = [
            "model=project.work.assignment",
            "res_id=%s" % assignment_rec.id,
        ]
        if action:
            params.append("action_id=%s" % action.id)
        if form_view:
            params.append("view_id=%s" % form_view.id)

        return "/project_work_assignment_notify/open_message_report?%s" % "&".join(params)

    def _get_assignment_fallback_url(self, field_name):
        self.ensure_one()

        conf = self._assignment_notify_role_map().get(field_name, {})
        action_xmlid = conf.get("action_xmlid")
        action = self.env.ref(action_xmlid, raise_if_not_found=False) if action_xmlid else False

        params = ["model=project.work.assignment"]
        if action:
            params.append("action_id=%s" % action.id)

        return "/project_work_assignment_notify/open_message_report?%s" % "&".join(params)

    # =========================================================
    # ONLINE POPUP
    # =========================================================
    def _assignment_notify_send_clickable(self, user, title, message, next_action=None):
        if not user or not user.partner_id:
            return

        self.env["bus.bus"]._sendone(
            user.partner_id,
            "project_work_item_assignment_notification",
            {
                "title": title,
                "message": message,
                "sticky": False,
                "next_action": next_action or {},
            }
        )

    # =========================================================
    # CHATTER / INBOX
    # =========================================================
    def _assignment_notify_post_chatter_grouped(self, user, field_names, role_labels):
        self.ensure_one()
        if not user or not user.partner_id:
            return

        assigner_name = self.env.user.display_name or _("Hệ thống")
        work_item_name = self.display_name or getattr(self, "name", "") or _("(Không có tên)")
        project_name = self.project_id.display_name if getattr(self, "project_id", False) else _("(Không có dự án)")
        role_text = ", ".join(role_labels)

        field_name = field_names[0]
        assignment_rec = self._find_related_assignment_record(field_name, user)

        if assignment_rec:
            record_url = self._get_assignment_record_url(field_name, assignment_rec)
            link_label = _("Mở phiếu báo cáo")
            target_record = assignment_rec if hasattr(assignment_rec, "message_post") else self
        else:
            record_url = self._get_assignment_fallback_url(field_name)
            link_label = _("Mở màn hình báo cáo")
            target_record = self

        body = Markup("""
            <p><b>Phân công báo cáo</b></p>
            <p><b>%s</b> đã phân công cho bạn vai trò: <b>%s</b>.</p>
            <p>Hạng mục: <b>%s</b></p>
            <p>Dự án: <b>%s</b></p>
            <p><a href="%s">%s</a></p>
        """) % (
            html_escape(assigner_name),
            html_escape(role_text),
            html_escape(work_item_name),
            html_escape(project_name),
            html_escape(record_url),
            html_escape(link_label),
        )

        try:
            target_record.message_post(
                body=body,
                partner_ids=[user.partner_id.id],
                subtype_xmlid="mail.mt_comment",
                message_type="comment",
            )
        except Exception:
            pass

    # =========================================================
    # SEND SINGLE GROUPED
    # =========================================================
    def _assignment_notify_send_single_grouped(self, new_user, field_names, role_labels):
        self.ensure_one()
        if not new_user:
            return

        assigner_name = self.env.user.display_name or _("Hệ thống")
        work_item_name = self.display_name or getattr(self, "name", "") or _("(Không có tên)")
        project_name = self.project_id.display_name if getattr(self, "project_id", False) else _("(Không có dự án)")
        role_text = ", ".join(role_labels)

        message = _(
            "%(assigner)s đã phân công bạn phụ trách %(roles)s cho hạng mục '%(work_item)s' thuộc dự án '%(project)s'."
        ) % {
            "assigner": assigner_name,
            "roles": role_text,
            "work_item": work_item_name,
            "project": project_name,
        }

        next_action = self._get_assignment_next_action(field_names[0], new_user)

        self._assignment_notify_send_clickable(
            new_user,
            _("Bạn được phân công báo cáo"),
            message,
            next_action=next_action,
        )

        self._assignment_notify_post_chatter_grouped(new_user, field_names, role_labels)

    # =========================================================
    # COMPARE OLD / NEW
    # =========================================================
    def _assignment_notify_after_write(self, old_map):
        tracked_fields = self._assignment_notify_tracked_fields()

        for rec in self:
            old_vals = old_map.get(rec.id, {})
            changes_by_user = {}

            for field_name in tracked_fields:
                new_user = rec[field_name] if field_name in rec._fields else False
                new_user_id = new_user.id if new_user else False
                old_user_id = old_vals.get(field_name)

                if new_user_id and new_user_id != old_user_id:
                    conf = rec._assignment_notify_role_map().get(field_name, {})
                    role_label = conf.get("label") or _("phụ trách")

                    if new_user_id not in changes_by_user:
                        changes_by_user[new_user_id] = {
                            "user": new_user,
                            "field_names": [],
                            "role_labels": [],
                        }

                    changes_by_user[new_user_id]["field_names"].append(field_name)
                    changes_by_user[new_user_id]["role_labels"].append(role_label)

            for data in changes_by_user.values():
                rec._assignment_notify_send_single_grouped(
                    data["user"],
                    data["field_names"],
                    data["role_labels"],
                )

    # =========================================================
    # ORM OVERRIDE
    # =========================================================
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        old_map = {
            rec.id: {
                "assigned_user_id": False,
                "claim_user_id": False,
                "acceptance_user_id": False,
            }
            for rec in records
        }

        try:
            records._assignment_notify_after_write(old_map)
        except Exception:
            pass

        return records

    def write(self, vals):
        tracked_fields = set(self._assignment_notify_tracked_fields())
        need_notify = bool(tracked_fields.intersection(vals.keys()))

        old_map = {}
        if need_notify:
            old_map = self._assignment_notify_prepare_old_map()

        res = super().write(vals)

        if need_notify:
            try:
                self._assignment_notify_after_write(old_map)
            except Exception:
                pass

        return res