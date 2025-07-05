from odoo import models, fields, api

class CostEstimate(models.Model):
    _name = 'cost.estimate'
    _description = 'Dự toán chi phí Dự án'

    name = fields.Char('Tên dự toán', required=True, default='New')
    project_id = fields.Many2one('project.project', string='Dự án', ondelete='restrict')
    sale_order_id = fields.Many2one('sale.order', string='Đơn hàng', ondelete='restrict')
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', required=True, default=lambda self: self.env.company.currency_id)
    total_cost = fields.Monetary(
        string='Tổng chi phí',
        compute='_compute_total_cost',
        store=False,
        currency_field='currency_id'
    )
    line_ids = fields.One2many('cost.estimate.line', 'cost_estimate_id', string='Chi tiết dự toán')

    @api.depends('line_ids.price_subtotal')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum(line.price_subtotal for line in rec.line_ids)