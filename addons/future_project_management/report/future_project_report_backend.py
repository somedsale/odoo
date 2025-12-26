from odoo import models


class ReportFutureProject(models.AbstractModel):
    _name = "report.future_project_management.future_project_report"
    _description = "Future Project Report Backend"

    def _get_report_values(self, docids, data=None):
        wizard = self.env["future.project.report.wizard"].browse(docids)
        wizard.ensure_one()

        start, end = wizard._get_date_range()

        projects = self.env["future.project"].search([
            ("expected_bid_date", ">=", start),
            ("expected_bid_date", "<=", end),
        ])

        won_projects = projects.filtered(lambda p: p.stage_id.is_won)

        return {
            "docs": projects,
            "start_date": start,
            "end_date": end,
            "total_projects": len(projects),
            "won_projects": len(won_projects),
            "win_rate": round((len(won_projects) / len(projects) * 100), 2)
            if projects else 0,
            "total_value": sum(projects.mapped("expected_value")),
        }
