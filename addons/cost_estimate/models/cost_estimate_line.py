from odoo import models, fields, api

class CostEstimateLine(models.Model):
    _name = 'cost.estimate.line'
    _description = 'Chi tiết dự toán'

    cost_estimate_id = fields.Many2one('cost.estimate', string='Dự toán', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Sản phẩm', ondelete='set null')
    quantity = fields.Float('Số lượng', default=1.0)
    price_unit = fields.Monetary('Đơn giá', currency_field='currency_id', default=0.0)  # Người dùng nhập thủ công
    price_subtotal = fields.Monetary(
        'Thành tiền',
        compute='_compute_price_subtotal',
        store=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one('res.currency', related='cost_estimate_id.currency_id', store=True, readonly=True)

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for rec in self:
            rec.price_subtotal = rec.quantity * rec.price_unit
    def open_material_list(self):
        self.ensure_one()
        return {
            'name': 'Danh sách vật tư - %s' % self.product_id.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'product.material.line',  # Model vật tư của bạn
            'view_mode': 'tree,form',
            'domain': [('product_id', '=', self.product_id.id)],
            'context': {'default_product_id': self.product_id.id},
            'target': 'current',  # hoặc 'new' nếu muốn popup
        }
