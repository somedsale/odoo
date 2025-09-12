from odoo import models, fields, api
class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.model
    def create(self, vals):
        project = super().create(vals)
        # Tạo bản ghi ProjectExpenseCustom khi tạo dự án mới
        self.env['project.expense.custom'].create_or_update_expense(project.id)
        return project
