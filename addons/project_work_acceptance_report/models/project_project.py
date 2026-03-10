# -*- coding: utf-8 -*-
from odoo import fields, models,api, _
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = "project.project"

    acceptance_report_count = fields.Integer(
        string="Báo cáo nghiệm thu",
        compute="_compute_acceptance_report_count",
    )
    acceptance_user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo nghiệm thu",
        tracking=True,
        help="Người phụ trách báo cáo nghiệm thu cho dự án.",
    )
    claim_user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo thanh / quyết toán",
        tracking=True,
        help="Người phụ trách báo cáo thanh / quyết toán cho dự án.",
    )
    assigned_user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo sản lượng",
        tracking=True,
        help="Người phụ trách báo cáo sản lượng cho dự án.",
    )
    assignment_ids = fields.One2many(
        "project.work.assignment",
        "project_id",
        string="Các phân công công việc",
    )
    acceptance_value_done = fields.Float(
        string="Giá trị nghiệm thu lũy kế",
        compute="_compute_acceptance_totals",
        store=False,
    )
    acceptance_value_remaining = fields.Float(
        string="Giá trị nghiệm thu còn lại",
        compute="_compute_acceptance_totals",
        store=False,
    )
    acceptance_progress_percent = fields.Float(
        string="% nghiệm thu",
        related="work_item_ids.acceptance_progress_percent",
        store=False,
    )
    @api.depends("work_item_ids.acceptance_value_done", "work_item_ids.acceptance_value_remaining", "work_item_ids")
    def _compute_acceptance_totals(self):
        for rec in self:
            rec.acceptance_value_done = sum(rec.work_item_ids.mapped("acceptance_value_done") or [0.0])
            rec.acceptance_value_remaining = sum(rec.work_item_ids.mapped("acceptance_value_remaining") or [0.0])
    @api.onchange("acceptance_user_id", "assigned_user_id", "claim_user_id")
    def _onchange_report_users(self):
        # ✅ không tự động gán người báo cáo nghiệm thu cho assignment nữa, để tránh vỡ quy trình nếu người dùng không muốn
        project_work_item_obj = self.env["project.work.item"]
        for rec in self:
            if rec.acceptance_user_id:
                # nếu có người báo cáo nghiệm thu ở project thì gán cho tất cả work item chưa có người báo cáo
                rec.assignment_ids.filtered(lambda a: not a.acceptance_user_id).write(
                    {"acceptance_user_id": rec.acceptance_user_id.id}
                )
                rec.work_item_ids.filtered(lambda w: not w.acceptance_user_id).write(
                    {"acceptance_user_id": rec.acceptance_user_id.id}
                )
            if rec.assigned_user_id:
                # nếu có người báo cáo sản lượng ở project thì gán cho tất cả work item chưa có người báo cáo
                rec.assignment_ids.filtered(lambda a: not a.user_id).write(
                    {"user_id": rec.assigned_user_id.id}
                )
                rec.work_item_ids.filtered(lambda w: not w.assigned_user_id).write(
                    {"assigned_user_id": rec.assigned_user_id.id}
                )
            if rec.claim_user_id:
                # nếu có người báo cáo thanh / quyết toán ở project thì gán cho tất cả work item chưa có người báo cáo
                rec.assignment_ids.filtered(lambda a: not a.claim_user_id).write(
                    {"claim_user_id": rec.claim_user_id.id}
                )
                rec.work_item_ids.filtered(lambda w: not w.claim_user_id).write(
                    {"claim_user_id": rec.claim_user_id.id}
                )
    def _compute_acceptance_report_count(self):
        # sudo để không làm vỡ form project vì lỗi quyền
        Assignment = self.env["project.work.assignment"].sudo()
        counts = {}
        if self.ids:
            data = Assignment.read_group(
                [
                    ("project_id", "in", self.ids),
                    ("active", "=", True),
                    ("acceptance_user_id", "!=", False),
                ],
                ["project_id"],
                ["project_id"],
            )
            counts = {
                d["project_id"][0]: d["project_id_count"]
                for d in data if d.get("project_id")
            }

        for rec in self:
            rec.acceptance_report_count = counts.get(rec.id, 0)

    def action_view_acceptance_reports(self):
        self.ensure_one()

        action = False
        for xmlid in [
            "project_work_acceptance_report.action_manager_assignment_acceptance_report",
            "project_work_acceptance_report.action_my_assignment_acceptance_report",
        ]:
            try:
                action = self.env.ref(xmlid).read()[0]
                break
            except Exception:
                continue

        if not action:
            raise UserError(_("Chưa tìm thấy action báo cáo nghiệm thu."))

        action["domain"] = [("project_id", "=", self.id), ("active", "=", True)]
        action["context"] = {
            "default_project_id": self.id,
        }
        return action