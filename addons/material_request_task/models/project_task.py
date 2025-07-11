# models/project_task.py

from odoo import models, fields,api

class ProjectTask(models.Model):
    _inherit = 'project.task'

    project_user_id = fields.Many2one(
        related='project_id.user_id',
        string='Trưởng dự án',
        store=False,
        readonly=True,
    )
    cost_estimate_line_ids = fields.One2many(
        'cost.estimate.line',
        'task_id',
        string='Dòng dự toán'
    )

    material_lines_from_estimate = fields.One2many(
        'product.material.line',
        compute='_compute_material_lines_from_estimate',
        string='Vật tư từ dự toán',
        store=False  # Chỉ dùng để hiển thị
    )

    @api.depends('cost_estimate_line_ids.material_line_ids')
    def _compute_material_lines_from_estimate(self):
        for task in self:
            material_lines = self.env['product.material.line']
            for estimate_line in task.cost_estimate_line_ids:
                material_lines |= estimate_line.material_line_ids
            task.material_lines_from_estimate = material_lines
