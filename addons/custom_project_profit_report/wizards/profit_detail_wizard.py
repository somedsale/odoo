# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class ProjectProfitDetailWizard(models.TransientModel):
    _name = "profit.detail.wizard"
    _description = "Wizard chọn công trình in lãi lỗ chi tiết"

    project_id = fields.Many2one(
        "project.project",
        string="Chọn dự án",
        required=True,
        domain=[("active", "=", True)],
    )

    def action_print_report(self):
        """
        In báo cáo lãi lỗ chi tiết theo công trình
        """
        self.ensure_one()

        if not self.project_id:
            raise UserError("Vui lòng chọn công trình.")

        ProfitLost = self.env["project.profit.lost"]

        # Tìm hồ sơ lãi lỗ theo project
        profit_lost = ProfitLost.search(
            [("project_id", "=", self.project_id.id)],
            limit=1,
        )

        # Nếu chưa có thì tạo mới
        if not profit_lost:
            profit_lost = ProfitLost.create({
                "project_id": self.project_id.id,
            })

        # Recompute lại dữ liệu (nếu có hàm này)
        if hasattr(profit_lost, "_recompute_values"):
            profit_lost._recompute_values()

        # Gọi report QWeb
        return self.env.ref(
            "custom_project_profit_report.project_profit_detail_report"
        ).report_action(profit_lost)
