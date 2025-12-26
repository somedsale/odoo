from odoo import models, fields
from datetime import date
from dateutil.relativedelta import relativedelta


class FutureProjectReportWizard(models.TransientModel):
    _name = "future.project.report.wizard"
    _description = "Future Project Report Wizard"

    period_type = fields.Selection(
        [
            ("month", "Theo tháng"),
            ("quarter", "Theo quý"),
            ("year", "Theo năm"),
        ],
        default="month",
        required=True,
    )

    year = fields.Integer(
        string="Năm",
        default=lambda self: date.today().year,
        required=True,
    )

    month = fields.Selection(
        [(str(i), f"Tháng {i}") for i in range(1, 13)],
        string="Tháng",
    )

    quarter = fields.Selection(
        [
            ("1", "Quý I"),
            ("2", "Quý II"),
            ("3", "Quý III"),
            ("4", "Quý IV"),
        ],
        string="Quý",
    )

    def _get_date_range(self):
        self.ensure_one()

        if self.period_type == "month":
            start = date(self.year, int(self.month), 1)
            end = start + relativedelta(months=1, days=-1)

        elif self.period_type == "quarter":
            q = int(self.quarter)
            start = date(self.year, (q - 1) * 3 + 1, 1)
            end = start + relativedelta(months=3, days=-1)

        else:
            start = date(self.year, 1, 1)
            end = date(self.year, 12, 31)

        return start, end

    def action_view_html(self):
        return self.env.ref(
            "future_project_management.action_future_project_html"
        ).report_action(self)

    def action_print_pdf(self):
        return self.env.ref(
            "future_project_management.action_future_project_pdf"
        ).report_action(self)
