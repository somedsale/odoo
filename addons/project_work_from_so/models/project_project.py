# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from markupsafe import Markup, escape
from odoo.tools import html_escape

class ProjectProject(models.Model):
    _inherit = "project.project"
    _mail_post_access = "read"
    # =========================
    # FIELDS
    # =========================
    contract_id = fields.Many2one("contract.management", string="Hợp đồng")
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Đơn bán",
        related="contract_id.sale_order_id",
        store=True,
        readonly=True,
    )

    work_item_ids = fields.One2many(
        "project.work.item",
        "project_id",
        string="Hạng mục công việc",
    )

    value_settlement = fields.Monetary(
        string="Giá trị thực tế",
        compute="_compute_project_value_summary",
        store=True,
    )
    value_arise = fields.Monetary(
        string="Giá trị phát sinh",
        compute="_compute_project_value_summary",
        store=True,
    )
    value_completed = fields.Monetary(
        string="Giá trị hoàn thành",
        compute="_compute_project_progress_summary",
        store=True,
    )
    value_remaining = fields.Monetary(
        string="Giá trị còn lại",
        compute="_compute_project_progress_summary",
        store=True,
    )
    progress_percent = fields.Float(
        string="% Hoàn thành",
        compute="_compute_project_progress_summary",
        store=True,
    )

    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    task_count_custom = fields.Integer(
        string="Số nhiệm vụ",
        compute="_compute_task_count_custom",
    )
    work_item_count = fields.Integer(
        string="Số hạng mục công việc",
        compute="_compute_work_item_count",
    )

    assignment_user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo sản lượng",
        tracking=True,
        help="Người báo cáo sản lượng.",
    )

    cost_estimate_id = fields.One2many(
        "cost.estimate",
        "project_id",
        string="Dự toán chi phí",
    )
    total_cost_estimate = fields.Float(
        string="Tổng dự toán chi phí chưa thuế",
        related="cost_estimate_id.total_cost",
        store=True,
    )
    total_cost_with_tax_estimate = fields.Float(
        string="Tổng dự toán chi phí có thuế",
        related="cost_estimate_id.total_cost_with_tax",
        store=True,
    )
    amount_additional_expense_estimate = fields.Float(
        string="Tổng chi phí phát sinh dự toán chưa thuế",
        related="cost_estimate_id.amount_additional_expense",
        store=True,
    )
    amount_additional_expense_with_tax_estimate = fields.Float(
        string="Tổng chi phí phát sinh dự toán có thuế",
        related="cost_estimate_id.amount_additional_expense_with_tax",
        store=True,
    )
    total_final_non_tax_estimate = fields.Float(
        string="Tổng dự toán cuối cùng chưa thuế",
        related="cost_estimate_id.total_final_non_tax",
        store=True,
    )
    total_final_with_tax_estimate = fields.Float(
        string="Tổng dự toán cuối cùng có thuế",
        related="cost_estimate_id.total_final_tax",
        store=True,
    )
    cost_estimate_count = fields.Integer(
        string="Số dự toán chi phí",
        compute="_compute_cost_estimate_count",
    )

    project_expense_custom_id = fields.One2many(
        "project.expense.custom",
        "project_id",
        string="Chi phí dự án",
    )
    total_spent = fields.Float(
        string="Tổng đã chi",
        related="project_expense_custom_id.total_spent",
        store=True,
    )
    total_not_spent = fields.Float(
        string="Tổng chưa chi",
        related="project_expense_custom_id.total_not_spent",
        store=True,
    )
    total_cost_expense = fields.Float(
        string="Tổng chi phí theo dõi",
        related="project_expense_custom_id.total_cost",
        store=True,
    )
    total_spent_material = fields.Float(
        string="Đã chi NVL",
        related="project_expense_custom_id.total_spent_material",
        store=True,
    )
    total_spent_labor = fields.Float(
        string="Đã chi Nhân công",
        related="project_expense_custom_id.total_spent_labor",
        store=True,
    )
    total_spent_manufacturing = fields.Float(
        string="Đã chi Sản xuất chung",
        related="project_expense_custom_id.total_spent_manufacturing",
        store=True,
    )
    total_material = fields.Float(
        string="Tổng NVL",
        related="project_expense_custom_id.total_material",
        store=True,
    )
    total_labor = fields.Float(
        string="Tổng Nhân công",
        related="project_expense_custom_id.total_labor",
        store=True,
    )
    total_manufacturing = fields.Float(
        string="Tổng Sản xuất chung",
        related="project_expense_custom_id.total_manufacturing",
        store=True,
    )
    total_not_spent_material = fields.Float(
        string="Chưa chi NVL",
        related="project_expense_custom_id.total_not_spent_material",
        store=True,
    )
    total_not_spent_labor = fields.Float(
        string="Chưa chi Nhân công",
        related="project_expense_custom_id.total_not_spent_labor",
        store=True,
    )
    total_not_spent_manufacturing = fields.Float(
        string="Chưa chi Sản xuất chung",
        related="project_expense_custom_id.total_not_spent_manufacturing",
        store=True,
    )
    project_expense_custom_count = fields.Integer(
        string="Số bản ghi chi phí dự án",
        compute="_compute_project_expense_custom_count",
    )

    my_assignment_count = fields.Integer(
        string="Số hạng mục cần báo cáo",
        compute="_compute_my_assignment_count",
    )
    my_assignment_ids = fields.One2many(
        "project.work.assignment",
        "project_id",
        string="Hạng mục của tôi",
    )

    report_closed_period_no = fields.Integer(
        string="Kỳ chốt báo cáo",
        readonly=True,
        copy=False,
    )
    report_closed_date = fields.Date(
        string="Ngày chốt báo cáo",
        readonly=True,
        copy=False,
    )

    # =========================
    # HELPERS
    # =========================
    def _is_project_completed(self):
        self.ensure_one()
        stage_name = (self.stage_id.name or "").strip().lower() if self.stage_id else ""
        done_names = ["hoàn tất", "hoan tat", "done", "completed", "complete"]
        return stage_name in done_names

    def _compute_tax_included_amount(self, so_line, quantity, price_unit=None):
        self.ensure_one()
        if not so_line:
            return 0.0

        quantity = quantity or 0.0
        price_unit = price_unit if price_unit is not None else (so_line.price_unit or 0.0)

        currency = self.currency_id or self.env.company.currency_id
        product = so_line.product_id
        partner = self.partner_id

        if so_line.tax_id:
            tax_res = so_line.tax_id.compute_all(
                price_unit,
                currency=currency,
                quantity=quantity,
                product=product,
                partner=partner,
            )
            return tax_res.get("total_included", 0.0)

        return price_unit * quantity

    # =========================
    # COMPUTE
    # =========================
    def _compute_my_assignment_count(self):
        data = self.env["project.work.assignment"].read_group(
            [
                ("project_id", "in", self.ids),
                ("user_id", "=", self.env.user.id),
                ("active", "=", True),
            ],
            ["project_id"],
            ["project_id"],
        )
        mapped_data = {
            x["project_id"][0]: x["project_id_count"]
            for x in data
            if x.get("project_id")
        }
        for rec in self:
            rec.my_assignment_count = mapped_data.get(rec.id, 0)

    @api.depends(
        "work_item_ids.value_arise_tax",
        "work_item_ids.value_settlement_tax",
    )
    def _compute_project_value_summary(self):
        for rec in self:
            rec.value_arise = sum(rec.work_item_ids.mapped("value_arise_tax") or [0.0])
            rec.value_settlement = sum(
                rec.work_item_ids.mapped("value_settlement_tax") or [0.0]
            )

    @api.depends("task_ids")
    def _compute_task_count_custom(self):
        for rec in self:
            rec.task_count_custom = len(rec.task_ids)

    @api.depends(
        "work_item_ids.value_done_tax",
        "work_item_ids.value_remaining_tax",
        "work_item_ids.progress_percent",
    )
    def _compute_project_progress_summary(self):
        for rec in self:
            work_items = rec.work_item_ids.filtered(lambda w: w.active)
            rec.progress_percent = (
                sum(work_items.mapped("progress_percent") or [0.0]) / len(work_items)
                if work_items
                else 0.0
            )
            rec.value_completed = sum(work_items.mapped("value_done_tax") or [0.0])
            rec.value_remaining = sum(work_items.mapped("value_remaining_tax") or [0.0])

    @api.depends("project_expense_custom_id")
    def _compute_project_expense_custom_count(self):
        grouped = self.env["project.expense.custom"].read_group(
            [("project_id", "in", self.ids)],
            ["project_id"],
            ["project_id"],
        )
        count_map = {
            g["project_id"][0]: g["project_id_count"]
            for g in grouped
            if g.get("project_id")
        }
        for rec in self:
            rec.project_expense_custom_count = count_map.get(rec.id, 0)

    @api.depends("cost_estimate_id")
    def _compute_cost_estimate_count(self):
        grouped = self.env["cost.estimate"].read_group(
            [("project_id", "in", self.ids)],
            ["project_id"],
            ["project_id"],
        )
        count_map = {
            g["project_id"][0]: g["project_id_count"]
            for g in grouped
            if g.get("project_id")
        }
        for rec in self:
            rec.cost_estimate_count = count_map.get(rec.id, 0)

    @api.depends("work_item_ids")
    def _compute_work_item_count(self):
        for rec in self:
            rec.work_item_count = len(rec.work_item_ids.filtered(lambda w: w.active))

    # =========================
    # ACTIONS
    # =========================
    def action_view_tasks_custom(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nhiệm vụ"),
            "res_model": "project.task",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("project_id", "=", self.id)],
            "context": {
                "default_project_id": self.id,
                "default_company_id": self.company_id.id if self.company_id else False,
            },
            "target": "current",
        }

    def action_view_project_expense_custom(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Chi phí dự án"),
            "res_model": "project.expense.custom",
            "view_mode": "tree,form",
            "domain": [("project_id", "=", self.id)],
            "context": {
                "default_project_id": self.id,
                "default_name": self.name and f"Chi phí - {self.name}" or "New",
            },
            "target": "current",
        }
        if self.project_expense_custom_count == 1:
            expense = self.env["project.expense.custom"].search([("project_id", "=", self.id)], limit=1)
            if expense:
                action.update({
                    "view_mode": "form",
                    "res_id": expense.id,
                    "views": [(False, "form")],
                })
        return action

    def action_view_cost_estimates(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Dự toán chi phí"),
            "res_model": "cost.estimate",
            "view_mode": "tree,form",
            "domain": [("project_id", "=", self.id)],
            "context": {
                "default_project_id": self.id,
                "default_name": self.name and f"Dự toán - {self.name}" or "New",
                "default_sale_order_id": self.sale_order_id.id if self.sale_order_id else False,
            },
            "target": "current",
        }

        if self.cost_estimate_count == 1:
            estimate = self.env["cost.estimate"].search([("project_id", "=", self.id)], limit=1)
            if estimate:
                action.update({
                    "view_mode": "form",
                    "res_id": estimate.id,
                    "views": [(False, "form")],
                })
        return action

    def action_assign_project_report_user(self, user_id):
        self.ensure_one()

        if not user_id:
            raise UserError(_("Vui lòng chọn người phụ trách."))

        user = self.env["res.users"].browse(user_id).exists()
        if not user:
            raise UserError(_("Người phụ trách không tồn tại."))

        # chỉ gán theo project
        self.assignment_user_id = user.id

        # đồng bộ assignment nếu bạn đang dùng project.work.assignment
        work_items = self.work_item_ids.filtered(lambda w: w.active)
        self._ensure_assignments_for_work_items(work_items)

        assignments = self.env["project.work.assignment"].search([
            ("project_id", "=", self.id),
            ("active", "=", True),
        ])
        if assignments:
            assignments.write({"user_id": user.id})

        # chỉ gửi 1 thông báo theo project
        self._send_project_assignment_notification(user)

        return {
            "message": _("Đã cập nhật người phụ trách báo cáo sản lượng cho dự án và gửi thông báo."),
        }

    def _ensure_assignments_for_work_items(self, work_items):
        Assignment = self.env["project.work.assignment"]

        for project in self:
            assignee = project.assignment_user_id or project.user_id
            if not assignee:
                continue

            project_items = work_items.filtered(lambda w: w.project_id == project and w.active)
            if not project_items:
                continue

            existing_assignments = Assignment.search([
                ("project_id", "=", project.id),
                ("work_item_id", "in", project_items.ids),
                ("active", "=", True),
            ])
            existing_by_work_item = {ass.work_item_id.id: ass for ass in existing_assignments}

            to_create_assignment = []
            for item in project_items:
                ass = existing_by_work_item.get(item.id)
                if ass:
                    if ass.user_id != assignee:
                        ass.user_id = assignee.id
                    continue

                to_create_assignment.append({
                    "project_id": project.id,
                    "work_item_id": item.id,
                    "user_id": assignee.id,
                    "active": True,
                })

            if to_create_assignment:
                Assignment.create(to_create_assignment)

    def action_assign_project_report_user_multi(self, user_id):
        if not self:
            raise UserError(_("Vui lòng chọn ít nhất một dự án."))

        if not user_id:
            raise UserError(_("Vui lòng chọn người phụ trách."))

        user = self.env["res.users"].browse(user_id).exists()
        if not user:
            raise UserError(_("Người phụ trách không tồn tại."))

        Assignment = self.env["project.work.assignment"]

        updated_projects = 0
        updated_assignments = 0

        for project in self:
            # gán user báo cáo cho project
            project.assignment_user_id = user.id

            # đảm bảo có assignment cho toàn bộ work item active
            work_items = project.work_item_ids.filtered(lambda w: w.active)
            project._ensure_assignments_for_work_items(work_items)

            # đồng bộ toàn bộ assignment hiện có của project sang user mới
            assignments = Assignment.search([
                ("project_id", "=", project.id),
                ("active", "=", True),
            ])
            if assignments:
                assignments.write({"user_id": user.id})
                updated_assignments += len(assignments)

            # thêm follower + gửi thông báo cho từng project
            project._send_project_assignment_notification(user)
            updated_projects += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Phân công thành công"),
                "message": _(
                    "Đã phân công người báo cáo sản lượng cho %(project_count)s dự án, cập nhật %(assignment_count)s hạng mục."
                ) % {
                    "project_count": updated_projects,
                    "assignment_count": updated_assignments,
                },
                "type": "success",
                "sticky": False,
            },
        }
    def action_sync_work_items_from_so(self):
        WorkItem = self.env["project.work.item"]
        all_synced_items = WorkItem.browse()

        for project in self:
            if not project.sale_order_id:
                raise UserError(_("Dự án chưa có Đơn bán (sale_order_id)."))

            so = project.sale_order_id
            lines = so.order_line.sorted(key=lambda l: (l.sequence, l.id))

            existing_by_line = {
                wi.so_line_id.id: wi
                for wi in project.work_item_ids.filtered(lambda x: x.so_line_id)
            }

            seq = max(project.work_item_ids.mapped("sequence") or [0])
            to_create = []
            current_section_name = False

            for line in lines:
                if line.display_type == "line_section":
                    current_section_name = (line.name or "").strip() or False
                    continue

                if line.display_type == "line_note":
                    continue

                vals = {
                    "qty_plan": line.product_uom_qty or 0.0,
                    "name": line.product_display_name or line.product_id.display_name or line.product_id.name,
                    "description": line.name,
                    "uom_id": line.product_uom.id if line.product_uom else False,
                    "product_id": line.product_id.id if line.product_id else False,
                    "section_name": current_section_name,
                }

                if line.id in existing_by_line:
                    wi = existing_by_line[line.id]
                    wi.write(vals)
                    all_synced_items |= wi
                    continue

                seq += 1
                vals.update({
                    "project_id": project.id,
                    "sequence": seq,
                    "so_line_id": line.id,
                    "active": True,
                })
                to_create.append(vals)

            if to_create:
                new_items = WorkItem.create(to_create)
                all_synced_items |= new_items

        if all_synced_items:
            self._ensure_assignments_for_work_items(all_synced_items)

        return True

    def get_formview_action(self, access_uid=None):
        self.ensure_one()
        if not self.env.context.get("open_work_custom"):
            return super().get_formview_action(access_uid=access_uid)

        action = self.env.ref("project_work_from_so.action_project_project_work_custom").read()[0]
        action["res_id"] = self.id
        action["view_mode"] = "form"
        action["views"] = [
            (self.env.ref("project_work_from_so.view_project_project_form_work_custom").id, "form")
        ]
        return action

    def action_open_work_dashboard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "project_work_project_dashboard",
            "context": {
                "active_id": self.id,
            },
        }

    def action_view_work_items(self):
        self.ensure_one()
        action = self.env.ref("project_work_from_so.action_project_work_item_list").read()[0]
        action["domain"] = [("project_id", "=", self.id)]
        action["context"] = {
            "default_project_id": self.id,
            "search_default_active_true": 1,
        }
        return action

    def action_open_my_assignment_report_owl(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "name": "Báo cáo sản lượng của tôi",
            "tag": "project_work_from_so.MyAssignmentReport",
            "target": "current",
            "context": {
                "default_project_id": self.id,
            },
        }

    def action_open_manager_assignment_report_owl(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "name": "Báo cáo sản lượng quản lý",
            "tag": "project_work_from_so.MyAssignmentReport",
            "target": "current",
            "context": {
                "default_project_id": self.id,
                "manager_mode": True,
            },
        }
    # =========================
    # OWL API
    # =========================
    def get_assignment_report_rows(self, manager_mode=False):
        self.ensure_one()

        Assignment = self.env["project.work.assignment"]
        Progress = self.env["project.work.progress"]

        rows_by_period = {}
        period_set = set()
        current_period_no = 0
        project_completed = self._is_project_completed()

        if manager_mode:
            work_items = self.work_item_ids.filtered(lambda w: w.active).sorted(
                key=lambda w: ((w.section_name or ""), w.sequence or 0, w.id)
            )

            assignments = Assignment.search([
                ("project_id", "=", self.id),
                ("active", "=", True),
            ])

            assignment_by_work_item = {}
            for ass in assignments:
                assignment_by_work_item.setdefault(ass.work_item_id.id, []).append(ass)

            display_records = []
            for work_item in work_items:
                ass_list = assignment_by_work_item.get(work_item.id, [])
                if ass_list:
                    for ass in ass_list:
                        display_records.append({
                            "assignment": ass,
                            "work_item": work_item,
                        })
                else:
                    display_records.append({
                        "assignment": False,
                        "work_item": work_item,
                    })
        else:
            assignments = Assignment.search([
                ("project_id", "=", self.id),
                ("user_id", "=", self.env.user.id),
                ("active", "=", True),
            ], order="id")

            display_records = [
                {
                    "assignment": ass,
                    "work_item": ass.work_item_id,
                }
                for ass in assignments
            ]

        for rec_data in display_records:
            ass = rec_data["assignment"]
            work_item = rec_data["work_item"]

            qty_plan = work_item.qty_plan or 0.0
            qty_arise = work_item.qty_arise or 0.0
            qty_settlement = work_item.qty_settlement or 0.0
            contract_qty = qty_settlement or qty_plan or 0.0
            max_total = contract_qty

            section_name = work_item.section_name or ""
            work_item_name = work_item.name or ""
            description = work_item.description or ""
            product = work_item.product_id
            uom = work_item.uom_id

            price_unit = work_item.price_unit or 0.0
            price_unit_tax = work_item.price_unit_tax or (
                self._compute_tax_included_amount(work_item.so_line_id, 1.0, price_unit=price_unit)
                if work_item.so_line_id else 0.0
            )

            assignee_name = "Chưa phân công"
            base_id = f"work_item_{work_item.id}"
            rec_current_period_no = 1
            rec_date_start = self.date_start

            if ass:
                assignee_name = ass.user_id.name or ""
                base_id = ass.id
                rec_current_period_no = ass.current_period_no or 1
                rec_date_start = ass.date_start or self.date_start

            current_period_no = max(current_period_no, rec_current_period_no or 0)

            line_map = {}
            if ass:
                lines = Progress.search(
                    [("assignment_id", "=", ass.id)],
                    order="period_no asc, id asc",
                )
                line_map = {ln.period_no: ln for ln in lines}
                max_line_period = max(line_map.keys()) if line_map else 0
                max_period = max(max_line_period, rec_current_period_no or 0, 1)
            else:
                max_period = max(rec_current_period_no or 0, 1)

            prev_cum = 0.0
            for period_no in range(1, max_period + 1):
                period_set.add(period_no)

                line = line_map.get(period_no) if ass else False
                qty_cum = line.qty_cum if line else prev_cum
                if qty_cum < prev_cum:
                    qty_cum = prev_cum

                qty_period = max(0.0, qty_cum - prev_cum)

                period_start = False
                period_end = False
                if rec_date_start and ass:
                    period_start, period_end = ass._get_period_bounds(rec_date_start, period_no)

                achieved_qty = qty_cum or 0.0
                prev_qty = prev_cum or 0.0
                current_qty = qty_period or 0.0

                if work_item.so_line_id:
                    contract_value_tax = self._compute_tax_included_amount(
                        work_item.so_line_id, contract_qty, price_unit=price_unit
                    )
                    prev_value_tax = self._compute_tax_included_amount(
                        work_item.so_line_id, prev_qty, price_unit=price_unit
                    )
                    current_value_tax = self._compute_tax_included_amount(
                        work_item.so_line_id, current_qty, price_unit=price_unit
                    )
                    current_value_cum_tax = self._compute_tax_included_amount(
                        work_item.so_line_id, achieved_qty, price_unit=price_unit
                    )
                else:
                    contract_value_tax = contract_qty * price_unit_tax
                    prev_value_tax = prev_qty * price_unit_tax
                    current_value_tax = current_qty * price_unit_tax
                    current_value_cum_tax = achieved_qty * price_unit_tax

                row = {
                    "id": base_id,
                    "assignment_id": ass.id if ass else False,
                    "work_item_id": work_item.id,
                    "period_no": period_no,
                    "section_name": section_name,
                    "assignment_name": assignee_name,
                    "work_item_name": work_item_name,
                    "description": description,
                    "product_name": product.display_name if product else "",
                    "uom_name": uom.display_name if uom else "",

                    "qty_plan": qty_plan,
                    "qty_arise": qty_arise,
                    "qty_settlement": qty_settlement,
                    "contract_qty": contract_qty,
                    "max_total": max_total,

                    "price_unit": price_unit,
                    "price_unit_tax": price_unit_tax,

                    "contract_value_tax": contract_value_tax,
                    "prev_qty_cum": prev_cum,
                    "current_qty_week": qty_period,
                    "current_note": (line.note if line else "") or "",
                    "current_qty_cum": qty_cum,
                    "qty_remaining": max(0.0, contract_qty - qty_cum) if contract_qty else 0.0,

                    "prev_value_tax": prev_value_tax,
                    "current_value_tax": current_value_tax,
                    "current_value_cum_tax": current_value_cum_tax,
                    "value_remaining_tax": max(0.0, contract_value_tax - current_value_cum_tax),

                    "current_period_no": rec_current_period_no or 0,
                    "period_start": period_start and period_start.isoformat() if period_start else False,
                    "period_end": period_end and period_end.isoformat() if period_end else False,
                    "is_current_period": (period_no == (rec_current_period_no or 0)) and not project_completed,
                    "is_editable": bool(ass) and not project_completed,
                    "is_unassigned": not bool(ass),
                }

                rows_by_period.setdefault(period_no, []).append(row)
                prev_cum = qty_cum

        available_periods = sorted(period_set)

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
                "my_assignment_count": len(display_records),
                "is_completed": project_completed,
                "manager_mode": bool(manager_mode),
                "contract_id": self.contract_id.id if self.contract_id else False,
                "sale_order_id": self.sale_order_id.id if self.sale_order_id else False,
                "assignment_user_id": self.assignment_user_id.id if self.assignment_user_id else False,
                "assignment_user_name": self.assignment_user_id.name if self.assignment_user_id else "",
                "value_contract_tax": self.value_contract_tax or 0.0,
                "value_settlement": self.value_settlement or 0.0,
                "value_arise": self.value_arise or 0.0,
                "value_completed": self.value_completed or 0.0,
                "value_remaining": self.value_remaining or 0.0,
                "progress_percent": self.progress_percent or 0.0,

                "total_cost_estimate": self.total_cost_estimate or 0.0,
                "total_cost_with_tax_estimate": self.total_cost_with_tax_estimate or 0.0,
                "amount_additional_expense_estimate": self.amount_additional_expense_estimate or 0.0,
                "amount_additional_expense_with_tax_estimate": self.amount_additional_expense_with_tax_estimate or 0.0,
                "total_final_non_tax_estimate": self.total_final_non_tax_estimate or 0.0,
                "total_final_with_tax_estimate": self.total_final_with_tax_estimate or 0.0,

                "total_spent": self.total_spent or 0.0,
                "total_not_spent": self.total_not_spent or 0.0,
                "total_cost_expense": self.total_cost_expense or 0.0,
                "total_spent_material": self.total_spent_material or 0.0,
                "total_spent_labor": self.total_spent_labor or 0.0,
                "total_spent_manufacturing": self.total_spent_manufacturing or 0.0,
                "total_material": self.total_material or 0.0,
                "total_labor": self.total_labor or 0.0,
                "total_manufacturing": self.total_manufacturing or 0.0,
                "total_not_spent_material": self.total_not_spent_material or 0.0,
                "total_not_spent_labor": self.total_not_spent_labor or 0.0,
                "total_not_spent_manufacturing": self.total_not_spent_manufacturing or 0.0,
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
                for user in self.env["res.users"].search([
                    ("share", "=", False),
                    ("groups_id", "in", [
                        self.env.ref("project.group_project_user").id,
                        self.env.ref("project.group_project_manager").id,
                    ]),
                ])
            ],
            "rows_by_period": rows_by_period,
            "available_periods": available_periods,
            "current_period_no": current_period_no,
        }

    def _compute_report_period_to_freeze(self):
        self.ensure_one()
        Assignment = self.env["project.work.assignment"]
        assignments = Assignment.search([
            ("project_id", "=", self.id),
            ("active", "=", True),
        ])

        if not assignments:
            return 1

        return max(assignments.mapped("current_period_no") or [1])

    def write(self, vals):
        res = super().write(vals)

        for rec in self:
            if rec._is_project_completed():
                if not rec.report_closed_period_no:
                    rec.report_closed_period_no = rec._compute_report_period_to_freeze()
                    rec.report_closed_date = fields.Date.context_today(rec)

        return res

    def save_assignment_report_rows(self, period_no, rows, manager_mode=False):
        self.ensure_one()

        if self._is_project_completed():
            raise UserError(_("Dự án đã hoàn tất, không được nhập hoặc chỉnh sửa báo cáo sản lượng."))

        if not isinstance(rows, list):
            raise UserError(_("Dữ liệu lưu không hợp lệ."))

        if not period_no:
            raise UserError(_("Thiếu thông tin kỳ báo cáo."))

        assignment_ids = [
            row.get("assignment_id") or row.get("id")
            for row in rows
            if row.get("assignment_id") or isinstance(row.get("id"), int)
        ]
        assignments = self.env["project.work.assignment"].browse(assignment_ids).exists()

        row_map = {}
        for row in rows:
            key = row.get("assignment_id") or row.get("id")
            if key:
                row_map[key] = row

        work_item_map = {}
        for row in rows:
            wid = row.get("work_item_id")
            if wid:
                work_item_map[wid] = row

        # Manager được sửa qty_arise trên work item
        if manager_mode and work_item_map:
            work_items = self.env["project.work.item"].browse(list(work_item_map.keys())).exists()
            for work_item in work_items:
                if work_item.project_id != self:
                    raise UserError(_("Bạn không có quyền cập nhật hạng mục này."))

                vals_wi = {}
                row_vals = work_item_map.get(work_item.id, {})

                if "qty_arise" in row_vals:
                    qty_arise = row_vals.get("qty_arise", 0.0)
                    qty_arise = 0.0 if qty_arise is False or qty_arise is None else float(qty_arise)
                    vals_wi["qty_arise"] = qty_arise

                if vals_wi:
                    work_item.write(vals_wi)

        # Lưu sản lượng kỳ hiện tại trên assignment
        for rec in assignments:
            if rec.project_id != self:
                raise UserError(_("Bạn không có quyền cập nhật hạng mục này."))

            if not manager_mode and rec.user_id != self.env.user:
                raise UserError(_("Bạn chỉ được cập nhật hạng mục của chính mình."))

            if rec.project_id._is_project_completed():
                raise UserError(_("Dự án đã hoàn tất, không được nhập hoặc chỉnh sửa báo cáo sản lượng."))

            if (rec.current_period_no or 0) != int(period_no):
                raise UserError(_("Chỉ được cập nhật kỳ hiện tại, không được sửa kỳ trước."))

            vals = row_map.get(rec.id, {})
            week_qty = vals.get("current_qty_week", 0.0) or 0.0
            note = vals.get("current_note", "") or ""

            if week_qty < 0:
                week_qty = 0.0

            rec.write({
                "current_qty_week": week_qty,
                "current_note": note,
            })

        self.invalidate_recordset()
        self.work_item_ids.invalidate_recordset()

        return self.get_assignment_report_rows(manager_mode=manager_mode)

    def _sync_work_items_from_so_batch(self):
        projects = self.sudo().search([
            ("sale_order_id", "!=", False),
        ])

        for project in projects:
            try:
                project.action_sync_work_items_from_so()
            except Exception:
                _logger.exception(
                    "Failed syncing work items from SO for project %s (%s)",
                    project.display_name,
                    project.id,
                )
        return True

    @api.model
    def cron_sync_all_work_items_from_so(self):
        return self._sync_work_items_from_so_batch()

    def action_assign_all_work_items(self, user_id, only_unassigned=False):
        self.ensure_one()

        if not user_id:
            raise UserError(_("Vui lòng chọn người phụ trách."))

        user = self.env["res.users"].browse(user_id).exists()
        if not user:
            raise UserError(_("Người phụ trách không tồn tại."))

        WorkItem = self.env["project.work.item"]
        Assignment = self.env["project.work.assignment"]

        work_items = WorkItem.search([
            ("project_id", "=", self.id),
            ("active", "=", True),
        ], order="section_name, sequence, id")

        existing_assignments = Assignment.search([
            ("project_id", "=", self.id),
            ("active", "=", True),
        ])

        assignment_by_work_item = {}
        for ass in existing_assignments:
            assignment_by_work_item.setdefault(ass.work_item_id.id, []).append(ass)

        to_create = []
        updated = 0
        created = 0

        for work_item in work_items:
            ass_list = assignment_by_work_item.get(work_item.id, [])

            if ass_list:
                if only_unassigned:
                    continue

                for ass in ass_list:
                    if ass.user_id.id != user.id:
                        ass.user_id = user.id
                        updated += 1
            else:
                to_create.append({
                    "project_id": self.id,
                    "work_item_id": work_item.id,
                    "user_id": user.id,
                    "active": True,
                })

        if to_create:
            Assignment.create(to_create)
            created = len(to_create)

        return {
            "created": created,
            "updated": updated,
            "message": _("Đã phân công %(created)s hạng mục mới, cập nhật %(updated)s hạng mục.") % {
                "created": created,
                "updated": updated,
            },
        }
    def _get_project_assignment_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "name": _("Báo cáo sản lượng của tôi"),
            "tag": "project_work_from_so.MyAssignmentReport",
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

    def _send_project_assignment_notification(self, user):
        self.ensure_one()
        if not user or not user.partner_id:
            return

        assigner_name = self.env.user.display_name or _("Hệ thống")
        project_name = self.display_name or self.name or _("(Không có tên dự án)")
        item_count = len(self.work_item_ids.filtered(lambda w: w.active))

        message = _(
            "%(assigner)s đã phân công bạn phụ trách báo cáo sản lượng cho dự án '%(project)s' (%(count)s hạng mục)."
        ) % {
            "assigner": assigner_name,
            "project": project_name,
            "count": item_count,
        }

        next_action = self._get_project_assignment_action()

        # popup realtime: chỉ gửi cho người được phân công
        self.env["bus.bus"]._sendone(
            user.partner_id,
            "project_work_project_assignment_notification",
            {
                "title": _("Bạn được phân công báo cáo sản lượng"),
                "message": message,
                "sticky": False,
                "next_action": next_action,
            },
        )

        # inbox/mail: chỉ gửi cho người được phân công, không post vào chatter dự án
        open_url = "/project_work_assignment_notify/open_my_assignment_report?project_id=%s" % self.id

        body = Markup("""
            <p><b>Phân công báo cáo sản lượng</b></p>
            <p><b>%s</b> đã phân công bạn phụ trách báo cáo sản lượng cho dự án <b>%s</b>.</p>
            <p>Số hạng mục áp dụng: <b>%s</b></p>
            <p><a href="%s">Mở báo cáo sản lượng</a></p>
        """) % (
            html_escape(assigner_name),
            html_escape(project_name),
            html_escape(str(item_count)),
            html_escape(open_url),
        )

        self.message_notify(
            partner_ids=[user.partner_id.id],
            subject=_("Bạn được phân công báo cáo sản lượng"),
            body=body,
            email_layout_xmlid="mail.mail_notification_light",
        )