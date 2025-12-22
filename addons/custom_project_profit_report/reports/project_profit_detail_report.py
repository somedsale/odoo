# -*- coding: utf-8 -*-
from odoo import models, api


class ProjectProfitDetailReportQweb(models.AbstractModel):
    """
    Report QWeb: Chi tiết lãi lỗ 1 công trình
    """
    _name = "report.custom_project_profit_report.project_profit_detail"
    _description = "QWeb Report - Project Profit Detail"
    _auto = False

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        docids: id của project.profit.lost (được truyền từ wizard)
        """
        ProfitLost = self.env["project.profit.lost"]
        profit = ProfitLost.browse(docids).exists()

        if not profit:
            return {"doc": False}

        # Recompute lại dữ liệu trước khi in
        if hasattr(profit, "_recompute_values"):
            profit._recompute_values()

        # 🔥 SORT CHI PHÍ THEO date_payment (tăng dần)
        detail_ids_sorted = profit.detail_ids.sorted(
            key=lambda l: l.date or False,
            reverse=True
        )

        return {
            "doc": profit,
            "project": profit.project_id,
            "company": self.env.company,

            # 🔥 TRUYỀN LIST ĐÃ SORT
            "detail_ids": detail_ids_sorted,
        }
