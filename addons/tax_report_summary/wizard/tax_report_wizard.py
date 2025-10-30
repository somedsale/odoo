# -*- coding: utf-8 -*-
from odoo import models, fields
from datetime import date
import calendar


class TaxReportWizard(models.TransientModel):
    _name = "tax.report.wizard"
    _description = "Báo cáo thuế đầu vào / đầu ra"

    # =============================
    #  CÁC LỰA CHỌN KIỂU XEM
    # =============================
    view_type = fields.Selection([
        ("period", "Khoảng thời gian tùy chọn"),
        ("month", "Theo tháng"),
        ("quarter", "Theo quý"),
        ("year", "Theo năm"),
    ], string="Kiểu xem báo cáo", default="period", required=True)

    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")

    month = fields.Selection(
        [(str(i), f"Tháng {i}") for i in range(1, 13)],
        string="Tháng"
    )

    quarter = fields.Selection([
        ("1", "Quý I (01–03)"),
        ("2", "Quý II (04–06)"),
        ("3", "Quý III (07–09)"),
        ("4", "Quý IV (10–12)"),
    ], string="Quý")

    year = fields.Char(
        string="Năm",
        required=True,
        default=lambda self: str(fields.Date.today().year)
    )

    # =============================
    #  HÀM TÍNH NGÀY TỰ ĐỘNG
    # =============================
    def _compute_date_range(self):
        """Trả về (date_from, date_to) theo view_type, month, quarter, year"""
        today = date.today()
        year = int(self.year or today.year)

        if self.view_type == "period":
            return (self.date_from, self.date_to)

        elif self.view_type == "month" and self.month:
            month = int(self.month)
            start = date(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end = date(year, month, last_day)
            return (start, end)

        elif self.view_type == "quarter" and self.quarter:
            q = int(self.quarter)
            start_month = (q - 1) * 3 + 1
            end_month = start_month + 2
            start = date(year, start_month, 1)
            last_day = calendar.monthrange(year, end_month)[1]
            end = date(year, end_month, last_day)
            return (start, end)

        elif self.view_type == "year":
            return (date(year, 1, 1), date(year, 12, 31))

        return (None, None)

    # =============================
    #  IN BÁO CÁO
    # =============================
    def action_print_report(self):
        date_from, date_to = self._compute_date_range()
        data = {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "view_type": self.view_type,  # 👈 truyền kiểu xem
        }
        return self.env.ref("tax_report_summary.action_report_tax_summary").report_action(self, data=data)

