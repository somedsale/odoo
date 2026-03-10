# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ProjectProject(models.Model):
    _inherit = "project.project"

    claim_report_count = fields.Integer(
        string="Báo cáo thanh / quyết toán",
        compute="_compute_claim_report_count",
    )

    # Giá trị quyết toán
    claim_value_done = fields.Float(
        string="Giá trị quyết toán lũy kế",
        compute="_compute_claim_totals",
        store=False,
    )
    claim_value_remaining = fields.Float(
        string="Giá trị quyết toán còn lại",
        compute="_compute_claim_totals",
        store=False,
    )
    claim_progress_percent = fields.Float(
        string="% quyết toán",
        related ="work_item_ids.claim_progress_percent",
        store=False,
    )

    @api.depends("work_item_ids.claim_value_done", "work_item_ids.claim_value_remaining", "work_item_ids")
    def _compute_claim_totals(self):
        for rec in self:
            rec.claim_value_done = sum(rec.work_item_ids.mapped("claim_value_done") or [0.0])
            rec.claim_value_remaining = sum(rec.work_item_ids.mapped("claim_value_remaining") or [0.0])

    @api.depends("work_item_ids.assignment_ids", "work_item_ids.assignment_ids.active")
    def _compute_claim_report_count(self):
        Assignment = self.env["project.work.assignment"]
        for rec in self:
            rec.claim_report_count = Assignment.search_count([
                ("project_id", "=", rec.id),
                ("active", "=", True),
            ])

    def action_view_claim_reports(self):
        """Mở danh sách báo cáo thanh/quyết toán (project.work.assignment) theo dự án."""
        self.ensure_one()

        # Ưu tiên action manager (xem tất cả), fallback action my report nếu chưa có
        action = False
        for xmlid in [
            "project_work_claim_report.action_manager_assignment_claim_report",
            "project_work_claim_report.action_my_assignment_claim_report",
        ]:
            try:
                action = self.env.ref(xmlid).read()[0]
                break
            except Exception:
                continue

        if not action:
            # fallback tự tạo action nếu chưa có XML action
            action = {
                "type": "ir.actions.act_window",
                "name": _("Báo cáo thanh / quyết toán"),
                "res_model": "project.work.assignment",
                "view_mode": "tree,form",
            }

        action["domain"] = [("project_id", "=", self.id), ("active", "=", True)]
        ctx = dict(self.env.context or {})
        ctx.update({
            "default_project_id": self.id,
            "search_default_active_true": 1,
        })
        action["context"] = ctx
        return action