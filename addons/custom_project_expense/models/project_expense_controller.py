from odoo import http
from odoo.http import request

class ProjectExpenseController(http.Controller):
    @http.route('/project_expense/statistics', type='json', auth='user')
    def get_statistics(self):
        domain = [('project_id', '!=', False)]
        records = request.env['project.expense'].search(domain)

        stats = []
        for record in records:
            stats.append({
                'project_name': record.project_id.name,
                'total_cost': record.total_cost,
                'total_spent': record.total_spent,
                'total_not_spent': record.total_not_spent,
            })

        return stats