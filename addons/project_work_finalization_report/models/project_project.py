# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.exceptions import UserError
from markupsafe import Markup
from odoo.tools import html_escape

class ProjectProject(models.Model):
    _inherit = "project.project"

    finalization_user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo thanh/quyết toán",
        tracking=True,
    )

    finalization_count = fields.Integer(
        string="Số hạng mục cần thanh/quyết toán",
        compute="_compute_finalization_count",
    )

    is_my_finalization_project = fields.Boolean(
        string="Là dự án thanh/quyết toán của tôi",
        compute="_compute_is_my_finalization_project",
        search="_search_is_my_finalization_project",
    )

    value_finalized = fields.Monetary(
        string="Giá trị đã thanh/quyết toán",
        compute="_compute_finalization_summary",
        store=True,
    )
    value_finalization_remaining = fields.Monetary(
        string="Giá trị còn lại chưa thanh/quyết toán",
        compute="_compute_finalization_summary",
        store=True,
    )
    finalization_percent = fields.Float(
        string="% thanh/quyết toán",
        compute="_compute_finalization_summary",
        store=True,
    )

    def _get_finalization_report_user(self, work_item):
        self.ensure_one()
        return work_item.finalization_user_id or self.finalization_user_id

    def _can_edit_finalization(self, work_item):
        self.ensure_one()
        user = self.env.user
        finalization_user = self._get_finalization_report_user(work_item)

        is_record_manager = self.user_id == user
        is_project_group_manager = user.has_group("project.group_project_manager")
        is_finalization_user = finalization_user == user if finalization_user else False

        return is_record_manager or is_project_group_manager or is_finalization_user

    @api.depends(
        "finalization_user_id",
        "work_item_ids.finalization_user_id",
        "work_item_ids.active",
    )
    def _compute_finalization_count(self):
        current_user = self.env.user
        for rec in self:
            count = 0
            for item in rec.work_item_ids.filtered(lambda x: x.active):
                finalization_user = item.finalization_user_id or rec.finalization_user_id
                if finalization_user == current_user:
                    count += 1
            rec.finalization_count = count

    @api.depends(
        "finalization_user_id",
        "work_item_ids.finalization_user_id",
        "work_item_ids.active",
    )
    def _compute_is_my_finalization_project(self):
        current_user = self.env.user
        for rec in self:
            is_mine = False
            for item in rec.work_item_ids.filtered(lambda x: x.active):
                finalization_user = item.finalization_user_id or rec.finalization_user_id
                if finalization_user == current_user:
                    is_mine = True
                    break
            rec.is_my_finalization_project = is_mine

    def _search_is_my_finalization_project(self, operator, value):
        if operator not in ("=", "!="):
            return []

        current_user = self.env.user

        item_project_ids = self.env["project.work.item"].search([
            ("active", "=", True),
            ("finalization_user_id", "=", current_user.id),
        ]).mapped("project_id").ids

        direct_project_ids = self.search([
            ("finalization_user_id", "=", current_user.id),
        ]).ids

        project_ids = list(set(item_project_ids + direct_project_ids)) or [0]

        if operator == "=":
            return [("id", "in" if value else "not in", project_ids)]
        return [("id", "not in" if value else "in", project_ids)]

    @api.depends(
        "work_item_ids.value_finalized_tax",
        "work_item_ids.value_finalization_remaining_tax",
        "work_item_ids.active",
    )
    def _compute_finalization_summary(self):
        for rec in self:
            items = rec.work_item_ids.filtered(lambda x: x.active)
            finalized = sum(items.mapped("value_finalized_tax") or [0.0])
            remaining = sum(items.mapped("value_finalization_remaining_tax") or [0.0])
            accepted_total = finalized + remaining

            rec.value_finalized = finalized
            rec.value_finalization_remaining = remaining
            rec.finalization_percent = (finalized / accepted_total * 100.0) if accepted_total else 0.0

    def _compute_tax_included_amount(self, so_line, quantity, price_unit=None):
        self.ensure_one()
        if not so_line:
            return (quantity or 0.0) * (price_unit or 0.0)

        quantity = quantity or 0.0
        price_unit = price_unit if price_unit is not None else (so_line.price_unit or 0.0)
        taxes = so_line.tax_id
        if not taxes:
            return quantity * price_unit

        currency = so_line.currency_id or self.company_id.currency_id
        partner = so_line.order_id.partner_shipping_id or so_line.order_id.partner_id
        product = so_line.product_id

        tax_res = taxes.compute_all(
            price_unit,
            currency=currency,
            quantity=quantity,
            product=product,
            partner=partner,
        )
        return tax_res.get("total_included", quantity * price_unit)

    def _is_project_completed(self):
        self.ensure_one()
        stage_name = (self.stage_id.name or "").strip().lower() if self.stage_id else ""
        done_names = ["hoàn tất", "hoan tat", "done", "completed", "complete"]
        return stage_name in done_names

    def _get_assignable_users(self):
        return self.env["res.users"].search([
            ("share", "=", False),
            ("groups_id", "in", [
                self.env.ref("project.group_project_user").id,
                self.env.ref("project.group_project_manager").id,
            ]),
        ])

    def action_assign_project_finalization_user(self, user_id):
        self.ensure_one()

        if not user_id:
            raise UserError(_("Vui lòng chọn người phụ trách thanh/quyết toán."))

        user = self.env["res.users"].browse(user_id).exists()
        if not user:
            raise UserError(_("Người phụ trách không tồn tại."))

        # Chỉ gán theo project, không ghi xuống từng hạng mục để tránh notify theo item
        self.finalization_user_id = user.id

        # Gửi 1 thông báo theo project
        self._send_project_finalization_assignment_notification(user)

        return {
            "message": _("Đã cập nhật người phụ trách thanh/quyết toán cho dự án và gửi thông báo."),
        }
    def _get_display_work_items_for_finalization(self, manager_mode=False):
        self.ensure_one()
        WorkItem = self.env["project.work.item"]

        items = WorkItem.search([
            ("project_id", "=", self.id),
            ("active", "=", True),
        ], order="section_name, sequence, id")

        if manager_mode:
            return items

        user = self.env.user
        return items.filtered(
            lambda item: (item.finalization_user_id or self.finalization_user_id) == user
        )

    def _ensure_finalization_line(self, assignment, period_no):
        self.ensure_one()
        Finalization = self.env["project.work.finalization"]

        line = Finalization.search([
            ("assignment_id", "=", assignment.id),
            ("period_no", "=", period_no),
        ], limit=1)

        if line:
            return line

        return Finalization.create({
            "project_id": self.id,
            "work_item_id": assignment.work_item_id.id,
            "assignment_id": assignment.id,
            "period_no": period_no,
            "date_start": assignment.date_start or self.date_start,
            "current_qty": 0.0,
            "note": "",
        })

    def get_finalization_report_rows(self, manager_mode=False):
        self.ensure_one()

        Finalization = self.env["project.work.finalization"]
        project_completed = self._is_project_completed()
        display_items = self._get_display_work_items_for_finalization(manager_mode=manager_mode)

        rows_by_period = {}
        period_set = set()
        current_period_no = 1

        for work_item in display_items:
            assignment = work_item.assignment_ids.filtered(lambda a: a.active)[:1]
            if not assignment:
                continue

            qty_plan = work_item.qty_plan or 0.0
            qty_arise = work_item.qty_arise or 0.0
            qty_settlement = qty_plan + qty_arise
            contract_qty = qty_settlement
            max_total = contract_qty

            # Mốc thanh/quyết toán phải bám theo đã nghiệm thu
            accepted_qty = work_item.qty_accepted or 0.0
            if accepted_qty < 0:
                accepted_qty = 0.0

            price_unit = work_item.price_unit or 0.0
            price_unit_tax = work_item.price_unit_tax or 0.0

            current_period_no = max(current_period_no, assignment.current_period_no or 1)

            finalization_lines = Finalization.search([
                ("assignment_id", "=", assignment.id),
                ("active", "=", True),
            ], order="period_no asc, id asc")

            line_map = {ln.period_no: ln for ln in finalization_lines}
            max_line_period = max(line_map.keys()) if line_map else 0
            max_period = max(max_line_period, assignment.current_period_no or 1, 1)

            prev_cum = 0.0
            for period_no in range(1, max_period + 1):
                period_set.add(period_no)
                line = line_map.get(period_no)

                current_qty = line.current_qty if line else 0.0
                qty_cum = prev_cum + (current_qty or 0.0)

                # Không cho lũy kế QT vượt quá khối lượng đã nghiệm thu
                qty_cum_limited = min(qty_cum, accepted_qty)
                prev_cum_limited = min(prev_cum, accepted_qty)
                current_qty_limited = max(0.0, qty_cum_limited - prev_cum_limited)

                period_start = False
                period_end = False
                if assignment.date_start:
                    period_start, period_end = assignment._get_period_bounds(
                        assignment.date_start, period_no
                    )

                if work_item.so_line_id:
                    contract_value_tax = self._compute_tax_included_amount(
                        work_item.so_line_id, contract_qty, price_unit=price_unit
                    )
                    accepted_value_tax = self._compute_tax_included_amount(
                        work_item.so_line_id, accepted_qty, price_unit=price_unit
                    )
                    prev_value_tax = self._compute_tax_included_amount(
                        work_item.so_line_id, prev_cum_limited, price_unit=price_unit
                    )
                    current_value_tax = self._compute_tax_included_amount(
                        work_item.so_line_id, current_qty_limited, price_unit=price_unit
                    )
                    current_value_cum_tax = self._compute_tax_included_amount(
                        work_item.so_line_id, qty_cum_limited, price_unit=price_unit
                    )
                else:
                    contract_value_tax = contract_qty * price_unit_tax
                    accepted_value_tax = accepted_qty * price_unit_tax
                    prev_value_tax = prev_cum_limited * price_unit_tax
                    current_value_tax = current_qty_limited * price_unit_tax
                    current_value_cum_tax = qty_cum_limited * price_unit_tax

                finalization_user = self._get_finalization_report_user(work_item)
                can_edit = self._can_edit_finalization(work_item)

                row = {
                    "id": f"fin_{assignment.id}_{period_no}",
                    "finalization_id": line.id if line else False,
                    "assignment_id": assignment.id,
                    "work_item_id": work_item.id,
                    "period_no": period_no,
                    "section_name": work_item.section_name or "",
                    "assignment_name": finalization_user.name if finalization_user else "",
                    "work_item_name": work_item.name or "",
                    "description": work_item.description or "",
                    "product_name": work_item.product_id.display_name if work_item.product_id else "",
                    "uom_name": work_item.uom_id.display_name if work_item.uom_id else "",
                    "qty_plan": qty_plan,
                    "qty_arise": qty_arise,
                    "qty_settlement": qty_settlement,
                    "contract_qty": contract_qty,
                    "accepted_qty": accepted_qty,
                    "max_total": max_total,
                    "price_unit": price_unit,
                    "price_unit_tax": price_unit_tax,
                    "contract_value_tax": contract_value_tax,
                    "accepted_value_tax": accepted_value_tax,
                    "prev_qty_cum": prev_cum_limited,
                    "current_qty_week": current_qty_limited,
                    "current_note": (line.note if line else "") or "",
                    "current_qty_cum": qty_cum_limited,
                    "qty_remaining": max(0.0, accepted_qty - qty_cum_limited),
                    "prev_value_tax": prev_value_tax,
                    "current_value_tax": current_value_tax,
                    "current_value_cum_tax": current_value_cum_tax,
                    "value_remaining_tax": max(0.0, accepted_value_tax - current_value_cum_tax),
                    "current_period_no": assignment.current_period_no or 1,
                    "period_start": period_start and period_start.isoformat() or False,
                    "period_end": period_end and period_end.isoformat() or False,
                    "is_current_period": (period_no == (assignment.current_period_no or 1)) and not project_completed,
                    "is_editable": can_edit and not project_completed,
                    "is_unassigned": not bool(finalization_user),
                }

                rows_by_period.setdefault(period_no, []).append(row)
                prev_cum = qty_cum

        available_periods = sorted(period_set) or [1]

        return {
            "project": {
                "id": self.id,
                "name": self.name,
                "partner_name": self.partner_id.display_name if self.partner_id else "",
                "manager_name": self.user_id.display_name if self.user_id else "",
                "stage_name": self.stage_id.name if self.stage_id else "",
                "date_start": self.date_start.isoformat() if self.date_start else False,
                "date_end": self.date.isoformat() if self.date else False,
                "contract_name": self.contract_id.display_name if self.contract_id else "",
                "num_contract": self.contract_id.num_contract if self.contract_id else False,
                "location": self.location if self.location else False,
                "finalization_count": len(display_items),
                "is_completed": project_completed,
                "manager_mode": bool(manager_mode),
                "finalization_user_id": self.finalization_user_id.id if self.finalization_user_id else False,
                "finalization_user_name": self.finalization_user_id.name if self.finalization_user_id else "",
                "value_contract_tax": self.value_contract_tax or 0.0,
                "value_settlement": self.value_settlement or 0.0,
                "value_arise": self.value_arise or 0.0,
                "value_finalized": self.value_finalized or 0.0,
                "value_finalization_remaining": self.value_finalization_remaining or 0.0,
                "finalization_percent": self.finalization_percent or 0.0,
                "attachments": [
                    {
                        "id": att.id,
                        "name": att.name or att.display_name or "Tệp đính kèm",
                        "mimetype": att.mimetype or "",
                        "url": f"/web/content/{att.id}?download=false",
                    }
                    for att in self.attachment_ids
                ],
            },
            "assignable_users": [
                {"id": user.id, "name": user.name}
                for user in self._get_assignable_users()
            ],
            "rows_by_period": rows_by_period,
            "available_periods": available_periods,
            "current_period_no": current_period_no,
        }

    def save_finalization_report_rows(self, period_no, rows, manager_mode=False):
        self.ensure_one()

        if not isinstance(rows, list):
            raise UserError(_("Dữ liệu lưu không hợp lệ."))

        if self._is_project_completed():
            raise UserError(_("Dự án đã hoàn tất, không được nhập hoặc chỉnh sửa báo cáo thanh/quyết toán."))

        if not period_no:
            raise UserError(_("Chưa xác định kỳ thanh/quyết toán."))

        row_map = {}
        assignment_ids = []
        for row in rows:
            assignment_id = row.get("assignment_id")
            if not assignment_id:
                continue
            row_map[assignment_id] = row
            assignment_ids.append(assignment_id)

        assignments = self.env["project.work.assignment"].browse(assignment_ids).exists()

        for assignment in assignments:
            if assignment.project_id != self:
                raise UserError(_("Có dữ liệu không thuộc dự án hiện tại."))

            work_item = assignment.work_item_id

            if not self._can_edit_finalization(work_item):
                raise UserError(_("Bạn không có quyền cập nhật thanh/quyết toán cho hạng mục này."))

            if int(assignment.current_period_no or 1) != int(period_no):
                raise UserError(_("Chỉ được cập nhật kỳ hiện tại, không được sửa kỳ trước."))

            vals = row_map.get(assignment.id, {})
            current_qty = vals.get("current_qty_week", 0.0) or 0.0
            note = vals.get("current_note", "") or ""

            if current_qty < 0:
                current_qty = 0.0

            accepted_qty = work_item.qty_accepted or 0.0

            prev_finalized = sum(
                assignment.finalization_line_ids.filtered(
                    lambda l: l.active and l.period_no < int(period_no)
                ).mapped("current_qty") or [0.0]
            )

            # Chỉ được QT tối đa trong phần đã nghiệm thu còn lại
            max_allowed = max(0.0, accepted_qty - prev_finalized)
            current_qty = min(current_qty, max_allowed)

            line = self._ensure_finalization_line(assignment, int(period_no))
            line.write({
                "current_qty": current_qty,
                "note": note,
            })

        self.invalidate_recordset()
        self.work_item_ids.invalidate_recordset()

        return self.get_finalization_report_rows(manager_mode=manager_mode)
    def _get_project_finalization_assignment_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "name": _("Báo cáo thanh/quyết toán của tôi"),
            "tag": "project_work_finalization_report.FinalizationReport",
            "target": "current",
            "context": {
                "default_project_id": self.id,
                "active_model": "project.project",
                "active_id": self.id,
                "active_ids": [self.id],
                "from_assignment_notification": 1,
                "manager_mode": False,
            },
        }
    def _send_project_finalization_assignment_notification(self, user):
        self.ensure_one()
        if not user or not user.partner_id:
            return

        assigner_name = self.env.user.display_name or _("Hệ thống")
        project_name = self.display_name or self.name or _("(Không có tên dự án)")
        item_count = len(self.work_item_ids.filtered(lambda w: w.active))

        message = _(
            "%(assigner)s đã phân công bạn phụ trách báo cáo thanh/quyết toán cho dự án '%(project)s' (%(count)s hạng mục)."
        ) % {
            "assigner": assigner_name,
            "project": project_name,
            "count": item_count,
        }

        next_action = self._get_project_finalization_assignment_action()

        # Popup realtime: chỉ gửi cho người được phân công
        self.env["bus.bus"]._sendone(
            user.partner_id,
            "project_work_project_finalization_assignment_notification",
            {
                "title": _("Bạn được phân công báo cáo thanh/quyết toán"),
                "message": message,
                "sticky": False,
                "next_action": next_action,
            }
        )

        # Inbox/mail: chỉ gửi cho người được phân công, không post vào chatter dự án
        try:
            open_url = "/project_work_assignment_notify/open_my_finalization_report?project_id=%s" % self.id

            body = Markup("""
                <p><b>Phân công báo cáo thanh/quyết toán</b></p>
                <p><b>%s</b> đã phân công bạn phụ trách báo cáo thanh/quyết toán cho dự án <b>%s</b>.</p>
                <p>Số hạng mục áp dụng: <b>%s</b></p>
                <p><a href="%s">Mở báo cáo thanh/quyết toán</a></p>
            """) % (
                html_escape(assigner_name),
                html_escape(project_name),
                html_escape(str(item_count)),
                html_escape(open_url),
            )

            self.message_notify(
                partner_ids=[user.partner_id.id],
                subject=_("Bạn được phân công báo cáo thanh/quyết toán"),
                body=body,
                email_layout_xmlid="mail.mail_notification_light",
            )
        except Exception:
            pass
    def action_assign_project_finalization_user_multi(self, user_id):
        if not self:
            raise UserError(_("Vui lòng chọn ít nhất một dự án."))

        if not user_id:
            raise UserError(_("Vui lòng chọn người phụ trách thanh/quyết toán."))

        user = self.env["res.users"].browse(user_id).exists()
        if not user:
            raise UserError(_("Người phụ trách không tồn tại."))

        updated_projects = 0
        updated_items = 0

        for project in self:
            project.finalization_user_id = user.id

            # Nếu muốn ép toàn bộ hạng mục active theo user mới thì giữ đoạn này
            active_items = project.work_item_ids.filtered(lambda w: w.active)
            if active_items and "finalization_user_id" in active_items._fields:
                active_items.write({"finalization_user_id": user.id})
                updated_items += len(active_items)

            project._send_project_finalization_assignment_notification(user)
            updated_projects += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Phân công thành công"),
                "message": _(
                    "Đã phân công người báo cáo thanh/quyết toán cho %(project_count)s dự án, cập nhật %(item_count)s hạng mục."
                ) % {
                    "project_count": updated_projects,
                    "item_count": updated_items,
                },
                "type": "success",
                "sticky": False,
            },
        }