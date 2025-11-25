# -*- coding: utf-8 -*-
from odoo import models, fields
from datetime import date
import calendar


class InputTaxReportWizard(models.TransientModel):
    _name = "input.tax.report.wizard"
    _description = "Báo cáo Thuế Đầu Vào"

    view_type = fields.Selection([
        ("period", "Khoảng thời gian tùy chọn"),
        ("month", "Theo tháng"),
        ("quarter", "Theo quý"),
        ("year", "Theo năm"),
    ], default="period")
    date_from = fields.Date()
    date_to = fields.Date()
    month = fields.Selection([(str(i), f"Tháng {i}") for i in range(1, 13)])
    quarter = fields.Selection([
        ("1", "Quý I"),
        ("2", "Quý II"),
        ("3", "Quý III"),
        ("4", "Quý IV"),
    ])
    year = fields.Char(default=lambda self: str(fields.Date.today().year))

    def _compute_date_range(self):
        today = date.today()
        year = int(self.year or today.year)

        if self.view_type == "period":
            return (self.date_from, self.date_to)

        if self.view_type == "month" and self.month:
            m = int(self.month)
            start = date(year, m, 1)
            end = date(year, m, calendar.monthrange(year, m)[1])
            return (start, end)

        if self.view_type == "quarter" and self.quarter:
            q = int(self.quarter)
            start_month = (q - 1) * 3 + 1
            end_month = start_month + 2
            start = date(year, start_month, 1)
            end = date(year, end_month, calendar.monthrange(year, end_month)[1])
            return (start, end)

        if self.view_type == "year":
            return (date(year, 1, 1), date(year, 12, 31))

        return (None, None)

    def action_print_report(self):
        date_from, date_to = self._compute_date_range()
        data = {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "view_type": self.view_type,
            "year": self.year,
            "month": self.month,
            "quarter": self.quarter,
        }
        return self.env.ref("tax_report_summary.action_report_input_tax").report_action(self, data=data)
