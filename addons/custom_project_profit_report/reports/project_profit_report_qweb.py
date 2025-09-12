from odoo import models

class ProjectProfitReportQweb(models.AbstractModel):
    _name = 'report.custom_project_profit_report.project_profit_template'  # trùng với report_name trong ir.actions.report
    _description = 'QWeb Report for Project Profit'

    def _get_report_values(self, docids=None, data=None):
        records = self.env['project.profit.report']._compute_records()
        return {
            'docs': records,
        }