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
    value_completed = fields.Monetary(string="Giá trị hoàn thành", compute="_compute_qty_done", store=True)
    value_remaining = fields.Monetary(string="Giá trị còn lại", compute="_compute_qty_done", store=True)
    progress_percent = fields.Float(string="% Hoàn thành", compute="_compute_qty_done", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    @api.depends("work_item_ids.value_completed", "work_item_ids.qty_plan", "work_item_ids.qty_done", "work_item_ids.progress_percent")
    def _compute_qty_done(self):
        for rec in self:
            total_plan = sum(rec.work_item_ids.mapped("qty_plan") or [0.0])
            total_done = sum(rec.work_item_ids.mapped("qty_done") or [0.0])
            rec.progress_percent = sum(rec.work_item_ids.mapped("progress_percent") or [0.0]) / len(rec.work_item_ids) if rec.work_item_ids else 0.0
            rec.value_completed = sum(rec.work_item_ids.mapped("value_completed") or [0.0])
            rec.value_remaining = sum(rec.work_item_ids.mapped("value_remaining") or [0.0])
    def action_sync_work_items_from_so(self):
        """Lấy hạng mục từ SO lines -> tạo work item (không tạo trùng theo so_line_id)."""
        for project in self:
            if not project.sale_order_id:
                raise UserError(_("Dự án chưa có Đơn bán (sale_order_id)."))

            so = project.sale_order_id
            lines = so.order_line.filtered(lambda l: not l.display_type)

            existing_by_line = {
                wi.so_line_id.id: wi
                for wi in project.work_item_ids.filtered(lambda x: x.so_line_id)
            }

            seq = max(project.work_item_ids.mapped("sequence") or [0])
            to_create = []
            for line in lines:
                if line.id in existing_by_line:
                    # cập nhật qty_plan nếu SO thay đổi
                    existing_by_line[line.id].qty_plan = line.product_uom_qty
                    continue
                seq += 1
                to_create.append(
                    {
                        "project_id": project.id,
                        "sequence": seq,
                        "name": line.product_display_name or line.product_id.name,
                        "description": line.name,
                        "so_line_id": line.id,
                        "product_id": line.product_id.id,
                        "uom_id": line.product_uom.id,
                        "qty_plan": line.product_uom_qty,
                        "active": True,
                    }
                )
            if to_create:
                self.env["project.work.item"].create(to_create)

        return True
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