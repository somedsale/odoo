# models/project_task.py
from odoo import models, fields, api, _
from datetime import date, timedelta, datetime
from odoo.exceptions import UserError

class ProjectTask(models.Model):
    _inherit = 'project.task'
    name = fields.Char(string='Nhiệm vụ', required=True)
    quantity = fields.Float(string='Quantity', default=0.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    quantity_uom = fields.Char(string='Tổng số lượng theo Hợp đồng', compute='_compute_quantity_uom', store=True, readonly=True)

    remaining_quantity = fields.Float(
        string='Sản lượng còn lại', compute='_compute_produced_quantity', store=True, readonly=True, default=0.0)
    production_report_ids = fields.One2many(
        'task.production.report', 'task_id', string='Production Reports')

    produced_quantity = fields.Float(
        string='Quantity Achieved', compute='_compute_produced_quantity', store=True,default=0.0)
    produced_quantity_uom = fields.Char(
        string='Sản lượng đã đạt được', compute='_compute_produced_quantity', store=True, readonly=True)
    remaining_quantity_uom= fields.Char(
        string='Sản lượng còn lại', compute='_compute_produced_quantity', store=True, readonly=True)
    completion_percent = fields.Float(
        string='Tiến độ (%)', compute='_compute_produced_quantity', store=True)
    deadline_status = fields.Selection([
        ('overdue', 'Quá hạn'),
        ('upcoming', 'Sắp hết hạn'),
        ('ontrack', 'Còn thời gian')
    ], string="Trạng thái Deadline", compute="_compute_deadline_status", store=True)

    @api.depends('quantity', 'uom_id')
    def _compute_quantity_uom(self):
        for task in self:
            if task.quantity and task.uom_id:
                task.quantity_uom = f"{task.quantity} {task.uom_id.name}"
            else:
                task.quantity_uom = ''
    @api.depends('production_report_ids.quantity_done')
    def _compute_produced_quantity(self):
        for task in self:
            total = sum(task.production_report_ids.mapped('quantity_done'))
            task.produced_quantity = total if total else 0.0
            task.remaining_quantity = (task.quantity - total) if task.quantity else 0.0
            task.completion_percent = (total / task.quantity * 100.0) if task.quantity else 0.0
            task.produced_quantity_uom = f"{task.produced_quantity} {task.uom_id.name}"
            task.remaining_quantity_uom = f"{task.remaining_quantity} {task.uom_id.name}"
    @api.depends('date_deadline')
    def _compute_deadline_status(self):
        today = fields.Date.today()
        for task in self:
            deadline = task.date_deadline
            if not deadline:
                task.deadline_status = False
            else:
                deadline_date = deadline.date() if isinstance(deadline, datetime) else deadline
                if deadline_date < today:
                    task.deadline_status = 'overdue'
                elif deadline_date <= today + timedelta(days=3):
                    task.deadline_status = 'upcoming'
                else:
                    task.deadline_status = 'ontrack'
    @api.model
    def create(self, vals):
        if not self.env.user.has_group('project.group_project_manager'):
            if 'user_ids' in vals or 'date_deadline' in vals:
                raise UserError(_("Bạn không có quyền chỉnh sửa những thông tin này."))
        return super().create(vals)

    def write(self, vals):
        if not self.env.user.has_group('project.group_project_manager'):
            if 'user_ids' in vals or 'date_deadline' in vals:
                raise UserError(_("Bạn không có quyền chỉnh sửa những thông tin này."))
        return super().write(vals)