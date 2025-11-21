from odoo import models, api

class ProjectProfitReportQweb(models.AbstractModel):
    _name = 'report.custom_project_profit_report.project_profit_template'
    _description = 'QWeb Report for Project Profit'

    @api.model
    def _get_report_values(self, docids=None, data=None):
        ProfitLost = self.env['project.profit.lost']

        # 1) Đồng bộ lại dữ liệu trước khi in (nếu muốn giống action_open_profit_lost)
        ProfitLost.load_all_projects()

        # 2) Lấy các bản ghi thỏa điều kiện giống trong model
        pls = ProfitLost.search([
            ('active', '=', True),
            ('project_id.is_internal_project2', '=', False),
            ('project_id', '!=', 4),
        ])

        # 3) Build lại list dict giống format bạn đang dùng trong QWeb
        records = []
        for rec in pls:
            records.append({
                'project_id': rec.project_id,           # dùng .name trong QWeb
                'num_contract': rec.num_contract,
                'contract_value': rec.contract_value,
                'revenue': rec.revenue,
                'material_cost': rec.material_cost,
                'labor_cost': rec.labor_cost,
                'other_cost': rec.other_cost,
                'expense': rec.expense,
                'profit': rec.profit,
            })

        return {
            'docs': records,
        }
