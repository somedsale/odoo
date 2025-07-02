from odoo import models, fields, api

class CostEstimate(models.Model):
    _name = 'cost.estimate'
    _description = 'Dự toán chi phí Dự án'

    name = fields.Char('Tên dự toán', required=True)
    project_id = fields.Many2one('project.project', string='Dự án', required=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        related='project_id.currency_id',
        readonly=True,
        store=True
    )
    total_cost = fields.Monetary(
        string='Tổng chi phí',
        compute='_compute_total_cost',
        store=True,
        currency_field='currency_id'
    )
    line_ids = fields.One2many('cost.estimate.line', 'cost_estimate_id', string='Chi tiết dự toán')

    @api.depends('line_ids.price_subtotal')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum(rec.line_ids.mapped('price_subtotal'))
