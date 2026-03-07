# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = "project.project"

    # Nếu bạn đã có contract_id ở module khác thì bỏ field này để tránh trùng tên
    contract_id = fields.Many2one("contract.management", string="Hợp đồng")
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Đơn bán",
        related="contract_id.sale_order_id",
        store=True,
        readonly=True,
    )

    work_item_ids = fields.One2many(
        "project.work.item", "project_id", string="Hạng mục công việc"
    )
    value_settlement = fields.Monetary(string="Giá trị thực tế", related="work_item_ids.value_settlement", store=True)
    value_arise = fields.Monetary(string="Giá trị phát sinh", related="work_item_ids.value_arise", store=True)
    value_completed = fields.Monetary(string="Giá trị hoàn thành", compute="_compute_qty_done", store=True)
    value_remaining = fields.Monetary(string="Giá trị còn lại", compute="_compute_qty_done", store=True)
    progress_percent = fields.Float(string="% Hoàn thành", compute="_compute_qty_done", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    task_count_custom = fields.Integer(
        string="Số nhiệm vụ",
        compute="_compute_task_count_custom",
    )
    work_item_count = fields.Integer(
        string="Số hạng mục công việc",
        compute="_compute_work_item_count",
    )
    cost_estimate_id = fields.One2many(
        "cost.estimate",
        "project_id",
        string="Dự toán chi phí",
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
    project_expense_custom_count = fields.Integer(
        string="Số bản ghi chi phí dự án",
        compute="_compute_project_expense_custom_count",
    )
    @api.depends('task_ids')
    def _compute_task_count_custom(self):
        for rec in self:
            rec.task_count_custom = len(rec.task_ids)

    def action_view_tasks_custom(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nhiệm vụ"),
            "res_model": "project.task",
            "view_mode": "list,form",  # hoặc tree,form vẫn được
            "views": [(False, "list"), (False, "form")],  # ✅ thêm dòng này
            "domain": [("project_id", "=", self.id)],
            "context": {
                "default_project_id": self.id,
                "default_company_id": self.company_id.id if self.company_id else False,
            },
            "target": "current",
        }
    @api.depends("work_item_ids.value_completed", "work_item_ids.qty_plan", "work_item_ids.qty_done", "work_item_ids.progress_percent")
    def _compute_qty_done(self):
        for rec in self:
            total_plan = sum(rec.work_item_ids.mapped("qty_plan") or [0.0])
            total_done = sum(rec.work_item_ids.mapped("qty_done") or [0.0])
            rec.progress_percent = sum(rec.work_item_ids.mapped("progress_percent") or [0.0]) / len(rec.work_item_ids) if rec.work_item_ids else 0.0
            rec.value_completed = sum(rec.work_item_ids.mapped("value_completed") or [0.0])
            rec.value_remaining = sum(rec.work_item_ids.mapped("value_remaining") or [0.0])
    @api.depends("project_expense_custom_id")
    def _compute_project_expense_custom_count(self):
        # Dùng read_group để đếm nhanh hơn count từng record
        grouped = self.env["project.expense.custom"].read_group(
            [("project_id", "in", self.ids)],
            ["project_id"],
            ["project_id"],
        )
        count_map = {g["project_id"][0]: g["project_id_count"] for g in grouped if g.get("project_id")}
        for rec in self:
            rec.project_expense_custom_count = count_map.get(rec.id, 0)
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
                # Nếu chỉ có 1 dự toán thì mở form luôn (tuỳ chọn)
        if self.cost_estimate_count == 1:
            estimate = self.env["cost.estimate"].search([("project_id", "=", self.id)], limit=1)
            if estimate:
                action.update({
                    "view_mode": "form",
                    "res_id": estimate.id,
                    "views": [(False, "form")],
                })
        return action
    @api.depends("cost_estimate_id")
    def _compute_cost_estimate_count(self):
        # Dùng read_group để đếm nhanh hơn count từng record
        grouped = self.env["cost.estimate"].read_group(
            [("project_id", "in", self.ids)],
            ["project_id"],
            ["project_id"],
        )
        count_map = {g["project_id"][0]: g["project_id_count"] for g in grouped if g.get("project_id")}
        for rec in self:
            rec.cost_estimate_count = count_map.get(rec.id, 0)

    def action_view_cost_estimates(self):
        self.ensure_one()

        # Nếu module cost_estimate của bạn đã có action list riêng thì thay XMLID bên dưới
        action = {
            "type": "ir.actions.act_window",
            "name": _("Dự toán chi phí"),
            "res_model": "cost.estimate",
            "view_mode": "tree,form",
            "domain": [("project_id", "=", self.id)],
            "context": {
                "default_project_id": self.id,
                "default_name": self.name and f"Dự toán - {self.name}" or "New",
                # nếu muốn auto fill SO theo project
                "default_sale_order_id": self.sale_order_id.id if self.sale_order_id else False,
            },
            "target": "current",
        }

        # Nếu chỉ có 1 dự toán thì mở form luôn (tuỳ chọn)
        if self.cost_estimate_count == 1:
            estimate = self.env["cost.estimate"].search([("project_id", "=", self.id)], limit=1)
            if estimate:
                action.update({
                    "view_mode": "form",
                    "res_id": estimate.id,
                    "views": [(False, "form")],
                })

        return action
    def action_sync_work_items_from_so(self):
        """Lấy hạng mục từ SO lines -> tạo work item (không tạo trùng theo so_line_id).
        Hỗ trợ line_section để gán tên danh mục cho các dòng sản phẩm bên dưới.
        """
        for project in self:
            if not project.sale_order_id:
                raise UserError(_("Dự án chưa có Đơn bán (sale_order_id)."))

            so = project.sale_order_id

            # ✅ Duyệt toàn bộ line theo đúng thứ tự để bắt section
            lines = so.order_line.sorted(key=lambda l: (l.sequence, l.id))

            existing_by_line = {
                wi.so_line_id.id: wi
                for wi in project.work_item_ids.filtered(lambda x: x.so_line_id)
            }

            seq = max(project.work_item_ids.mapped("sequence") or [0])
            to_create = []

            current_section_name = False  # ✅ giữ tên section hiện tại

            for line in lines:
                # 1) Nếu là section -> cập nhật danh mục hiện tại
                if line.display_type == "line_section":
                    current_section_name = (line.name or "").strip() or False
                    continue

                # 2) Nếu là note -> bỏ qua (không tạo hạng mục)
                if line.display_type == "line_note":
                    continue

                # 3) Dòng sản phẩm thật
                if line.id in existing_by_line:
                    wi = existing_by_line[line.id]

                    # cập nhật khi SO thay đổi
                    wi_vals = {
                        "qty_plan": line.product_uom_qty,
                        "name": line.product_display_name or line.product_id.display_name or line.product_id.name,
                        "description": line.name,
                        "uom_id": line.product_uom.id if line.product_uom else False,
                        "product_id": line.product_id.id if line.product_id else False,
                        # ✅ gán section vào work item
                        "section_name": current_section_name,
                    }
                    wi.write(wi_vals)
                    continue

                seq += 1
                to_create.append(
                    {
                        "project_id": project.id,
                        "sequence": seq,
                        "name": line.product_display_name or line.product_id.display_name or line.product_id.name,
                        "description": line.name,
                        "so_line_id": line.id,
                        "product_id": line.product_id.id,
                        "uom_id": line.product_uom.id,
                        "qty_plan": line.product_uom_qty,
                        "section_name": current_section_name,  # ✅ thêm section
                        "active": True,
                    }
                )

            if to_create:
                self.env["project.work.item"].create(to_create)
    def get_formview_action(self, access_uid=None):
        self.ensure_one()
        # Nếu không có flag thì giữ mặc định
        if not self.env.context.get("open_work_custom"):
            return super().get_formview_action(access_uid=access_uid)

        action = self.env.ref("project_work_from_so.action_project_project_work_custom").read()[0]
        action["res_id"] = self.id
        action["view_mode"] = "form"
        action["views"] = [(self.env.ref("project_work_from_so.view_project_project_form_work_custom").id, "form")]
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


    @api.depends("work_item_ids")
    def _compute_work_item_count(self):
        for rec in self:
            rec.work_item_count = len(rec.work_item_ids)

    def action_view_work_items(self):
        self.ensure_one()
        action = self.env.ref("project_work_from_so.action_project_work_item_list").read()[0]
        action["domain"] = [("project_id", "=", self.id)]
        action["context"] = {
            "default_project_id": self.id,
            "search_default_active_true": 1,
        }
        return action
