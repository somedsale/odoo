# models/project_task.py

from odoo import models, fields,api
import logging
_logger = logging.getLogger(__name__)

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

    approved_material_lines = fields.One2many(
        comodel_name='proposal.material.line',
        compute='_compute_approved_material_lines',
        string='Vật tư đã duyệt',
        store=False,
    )

    def _compute_approved_material_lines(self):
        for task in self:
            task.approved_material_lines = self.env['proposal.material.line'].search([
                ('sheet_id.task_id', '=', task.id),
                ('sheet_id.state', '=', 'approved')
            ])


    compare_material_html = fields.Html(
        compute='_compute_compare_material_html',
        string="So sánh vật tư",
        sanitize=False,
    )

    @api.depends('material_lines_from_estimate', 'approved_material_lines')
    def _compute_compare_material_html(self):
        for task in self:
            estimate_map = {
                line.material_id.id: line for line in task.material_lines_from_estimate
            }
            actual_map = {}
            for line in task.approved_material_lines:
                mid = line.material_id.id
                actual_map[mid] = actual_map.get(mid, 0) + line.quantity

            html = "<table class='table table-sm table-bordered'><thead><tr>" \
                   "<th>Vật tư</th><th>Dự toán</th><th>Đã duyệt</th><th>Chênh lệch</th><th>Ghi chú</th>" \
                   "</tr></thead><tbody>"

            for material_id in set(estimate_map.keys()).union(actual_map.keys()):
                est_line = estimate_map.get(material_id)
                est_qty = est_line.quantity if est_line else 0.0
                act_qty = actual_map.get(material_id, 0.0)
                diff = act_qty - est_qty
                note = 'Vượt' if diff > 0 else 'Còn dư' if diff < 0 else 'Đúng kế hoạch'
                material_name = est_line.material_id.name if est_line else self.env['project.material'].browse(material_id).name
                html += f"<tr><td>{material_name}</td><td>{est_qty}</td><td>{act_qty}</td><td>{diff}</td><td>{note}</td></tr>"

            html += "</tbody></table>"
            task.compare_material_html = html