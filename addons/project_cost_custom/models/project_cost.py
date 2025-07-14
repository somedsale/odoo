from odoo import models, fields, api

class TaskCostLine(models.Model):
    _name = 'project.task.cost.line'
    _description = 'Task Cost Line'

    task_id = fields.Many2one('project.task', string='Task', required=True, ondelete='cascade')
    name = fields.Char('Description', required=True)
    cost_type = fields.Selection([
        ('labor', 'Nhân công'),
        ('material', 'Vật tư'),
        ('outsource', 'Thuê ngoài'),
        ('other', 'Khác')
    ], string='Loại chi phí', required=True)
    quantity = fields.Float('Số lượng', default=1.0)
    price_unit = fields.Monetary('Đơn giá', required=True)
    price_subtotal = fields.Monetary('Thành tiền', compute='_compute_subtotal', store=True)
    currency_id = fields.Many2one('res.currency', related='task_id.project_id.currency_id', readonly=True)

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

class ProjectTask(models.Model):
    _inherit = 'project.task'

    cost_line_ids = fields.One2many('project.task.cost.line', 'task_id', string='Chi phí')
    amount_task_cost = fields.Monetary('Tổng chi phí task', compute='_compute_task_cost', store=True)
    currency_id = fields.Many2one('res.currency', related='project_id.currency_id', readonly=True)

    @api.depends('cost_line_ids.price_subtotal')
    def _compute_task_cost(self):
        for task in self:
            task.amount_task_cost = sum(line.price_subtotal for line in task.cost_line_ids)

class ProjectProject(models.Model):
    _inherit = 'project.project'

    amount_project_cost = fields.Monetary('Tổng chi phí dự án', compute='_compute_project_cost', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)

    @api.depends('task_ids.amount_task_cost')
    def _compute_project_cost(self):
        for project in self:
            project.amount_project_cost = sum(task.amount_task_cost for task in project.task_ids)
