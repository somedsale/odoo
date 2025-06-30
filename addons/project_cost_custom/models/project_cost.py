from odoo import models, fields, api

class ProjectCost(models.Model):
    _name = 'project.cost'
    _description = 'Project Cost'

    name = fields.Char(string='Tên chi phí', required=True)
    project_id = fields.Many2one('project.project', string='Dự án', required=True)
    cost_line_ids = fields.One2many('project.cost.line', 'cost_id', string='Chi phí phát sinh')
    total_actual_cost = fields.Monetary(string='Tổng chi phí thực tế', compute='_compute_total_actual_cost', store=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id)

    @api.depends('cost_line_ids.actual_amount')
    def _compute_total_actual_cost(self):
        for cost in self:
            cost.total_actual_cost = sum(line.actual_amount for line in cost.cost_line_ids)

class ProjectCostLine(models.Model):
    _name = 'project.cost.line'
    _description = 'Chi phí phát sinh dự án'

    cost_id = fields.Many2one('project.cost', string='Chi phí dự án', required=True, ondelete='cascade')
    name = fields.Char(string='Danh mục chi phí / Mô tả', required=True)
    actual_amount = fields.Monetary(string='Số tiền thực tế', required=True)
    date = fields.Date(string='Ngày phát sinh', default=fields.Date.context_today)
    note = fields.Text(string='Ghi chú')
    currency_id = fields.Many2one(related='cost_id.currency_id', store=True, readonly=True)
