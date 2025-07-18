from odoo import models, fields, api
class ProjectProject(models.Model):
    _inherit = 'project.project'

    completion_percent = fields.Float(
        string='Tiến độ (%)',
        compute='_compute_completion_percent',
        store=True,
        digits=(16, 2),
        default=0.0
    )

    @api.depends('task_ids.completion_percent')
    def _compute_completion_percent(self):
        for project in self:
            tasks = project.task_ids
            if tasks:
                total_completion = sum(tasks.mapped('completion_percent'))
                project.completion_percent = total_completion / len(tasks)
            else:
                project.completion_percent = 0.0