# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectWorkItem(models.Model):
    _name = "project.work.item"
    _description = "Project Work Item"
    _order = "sequence, id"

    project_id = fields.Many2one("project.project", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="project_id.company_id", store=True, readonly=True)

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    name = fields.Char(string="Tên hạng mục", required=True)
    so_line_id = fields.Many2one("sale.order.line", string="Dòng SO", readonly=True)
    
    product_id = fields.Many2one("product.product", string="Sản phẩm", required=True)
    uom_id = fields.Many2one("uom.uom", string="Đơn vị tính", required=True)
    description = fields.Text(string="Mô tả")
    qty_plan = fields.Float(string="Số lượng theo SO", digits="Product Unit of Measure", default=0.0)

    assigned_user_ids = fields.Many2many("res.users", string="Người phụ trách")

    assignment_ids = fields.One2many("project.work.assignment", "work_item_id", string="Phân công")
    price_unit = fields.Float(string="Đơn giá theo SO", related="so_line_id.price_unit", digits="Product Price", readonly=True)
    price_subtotal = fields.Monetary(string="Thành tiền theo SO", related="so_line_id.price_subtotal", store=True)
    qty_done = fields.Float(string="Đã thực hiện", compute="_compute_qty_done", store=True, digits="Product Unit of Measure")
    qty_remaining = fields.Float(string="Còn lại", compute="_compute_qty_done", store=True, digits="Product Unit of Measure")
    progress_percent = fields.Float(string="% Hoàn thành", compute="_compute_qty_done", store=True)
    value_completed = fields.Monetary(string="Giá trị hoàn thành", compute="_compute_qty_done", store=True)
    value_remaining = fields.Monetary(string="Giá trị còn lại", compute="_compute_qty_done", store=True)
    currency_id = fields.Many2one(related="project_id.company_id.currency_id", store=True, readonly=True)
    progress_line_ids = fields.One2many(
        "project.work.progress",
        "work_item_id",
        string="Lịch sử lũy kế",
    )
    @api.depends("qty_plan", "assignment_ids.qty_done", "price_unit")
    def _compute_qty_done(self):
        for rec in self:
            done = sum(rec.assignment_ids.mapped("qty_done") or [0.0])

            # ✅ cho phép vượt kế hoạch
            rec.qty_done = done

            # ✅ còn lại có thể âm (âm nghĩa là vượt)
            qty_remaining = (rec.qty_plan or 0.0) - done
            rec.qty_remaining = qty_remaining if qty_remaining > 0.0 else 0.0

            # ✅ % hoàn thành có thể > 100%
            if rec.qty_plan:
                rec.progress_percent = (done / rec.qty_plan) * 100.0
            else:
                # nếu không có plan: bạn có thể chọn 0 hoặc 100 tùy nghiệp vụ
                rec.progress_percent = 0.0

            # ✅ giá trị hoàn thành tính theo thực tế (có thể vượt)
            rec.value_completed = (done * rec.price_unit) if rec.price_unit else 0.0
            rec.value_remaining = rec.qty_remaining * rec.price_unit if rec.price_unit else 0.0


    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_assignments_from_assignees()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "assigned_user_ids" in vals:
            self._sync_assignments_from_assignees()
        return res
    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.uom_id = rec.product_id.uom_id
    def _sync_assignments_from_assignees(self):
        """Tạo assignment cho từng user trong assigned_user_ids (không tạo trùng)."""
        Assignment = self.env["project.work.assignment"]
        for wi in self:
            existing_users = set(wi.assignment_ids.mapped("user_id").ids)
            new_users = set(wi.assigned_user_ids.ids) - existing_users
            if not new_users:
                continue
            to_create = []
            for uid in new_users:
                to_create.append(
                    {
                        "project_id": wi.project_id.id,
                        "work_item_id": wi.id,
                        "user_id": uid,
                        "date_start": fields.Date.context_today(self),
                        "active": True,
                    }
                )
            if to_create:
                Assignment.create(to_create)
