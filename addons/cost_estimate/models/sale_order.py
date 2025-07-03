from odoo import models, api, fields
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cost_estimate_id = fields.Many2one('cost.estimate', string='Dự toán chi phí', readonly=True)

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if not order.cost_estimate_id:
                # Tạo dự toán tự động
                budget_vals = {
                    'name': f'Dự toán cho {order.name}',
                    'sale_order_id': order.id,
                    'project_id': order.project_id.id if order.project_id else False,
                    'currency_id': order.currency_id.id,
                    'line_ids': [(0, 0, {
                        'product_id': line.product_id.id,
                        'quantity': line.product_uom_qty,
                        'price_unit': 0.0,  # Để trống để người dùng nhập thủ công
                    }) for line in order.order_line if line.product_id],
                }
                cost_estimate = self.env['cost.estimate'].create(budget_vals)
                order.cost_estimate_id = cost_estimate.id
        return res