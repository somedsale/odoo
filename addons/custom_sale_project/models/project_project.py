from odoo import models, fields, api
from datetime import date, timedelta, datetime
class ProjectProject(models.Model):
    _inherit = 'project.project'

    completion_percent = fields.Float(
        string='Tiến độ (%)',
        compute='_compute_completion_percent',
        store=True,
        digits=(16, 2),
        default=0.0
    )
    deadline_status = fields.Selection([
        ('overdue', 'Quá hạn'),
        ('upcoming', 'Sắp hết hạn'),
        ('ontrack', 'Còn thời gian')
    ], string="Trạng thái Deadline", compute='_compute_deadline_status', store=True)

    @api.depends('task_ids.completion_percent')
    def _compute_completion_percent(self):
        for project in self:
            tasks = project.task_ids
            if tasks:
                total_completion = sum(tasks.mapped('completion_percent'))
                project.completion_percent = total_completion / len(tasks)
            else:
                project.completion_percent = 0.0
    @api.depends('date')
    def _compute_deadline_status(self):
        today = fields.Date.today()
        for project in self:
            deadline = project.date  # Sử dụng trường 'date' làm ngày kết thúc dự án
            if not deadline:
                project.deadline_status = False
            else:
                deadline_date = deadline.date() if isinstance(deadline, datetime) else deadline
                if deadline_date < today:
                    project.deadline_status = 'overdue'
                elif deadline_date <= today + timedelta(days=3):
                    project.deadline_status = 'upcoming'
                else:
                    project.deadline_status = 'ontrack'