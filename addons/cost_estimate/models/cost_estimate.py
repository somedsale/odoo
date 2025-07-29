from odoo import models, fields, api

class CostEstimate(models.Model):
    _name = 'cost.estimate'
    _description = 'Dự toán chi phí Dự án'
    _order = "create_date desc"

    code = fields.Char('Mã dự toán', required=True, copy=False, readonly=True,
         help='Mã định danh duy nhất của dự toán chi phí',default='New')
    name = fields.Char('Tên dự toán', required=True, default='New')
    project_id = fields.Many2one('project.project', string='Dự án', ondelete='restrict')
    sale_order_id = fields.Many2one('sale.order', string='Đơn hàng', ondelete='restrict')
    line_ids = fields.One2many('cost.estimate.line', 'cost_estimate_id', string='Chi tiết dự toán')
    total_cost = fields.Float(
        string='Tổng chi phí',
        compute='_compute_total_cost',
        store=True,
        digits=(16, 0)
    )

    @api.depends('line_ids.price_subtotal')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum(line.price_subtotal for line in rec.line_ids)
    @api.model
    def create(self, vals):
        if not vals.get('code'):
            vals['code'] = self.env['ir.sequence'].next_by_code('cost.estimate.code') or '/'
        return super().create(vals)