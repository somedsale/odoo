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
    
    def action_generate_lines_from_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            return
        
        # Xóa dòng cũ nếu có
        self.line_ids.unlink()

        for so_line in self.sale_order_id.order_line:
            self.env['cost.estimate.line'].create({
                'cost_estimate_id': self.id,
                'product_id': so_line.product_id.id,
                'quantity': so_line.product_uom_qty,
                'price_unit': so_line.price_unit,
            })
