from odoo import models, fields, api
class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.model
    def create(self, vals):
        project = super().create(vals)
        # Tạo bản ghi ProjectProfitLost khi tạo dự án mới
        self.env['project.profit.lost'].create_or_update(project.id)
        return project
