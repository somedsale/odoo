from odoo import models, fields, api
class CostEstimateLine(models.Model):
    _name = 'cost.estimate.line'
    _description = 'Chi tiết dự toán'

    cost_estimate_id = fields.Many2one('cost.estimate', string='Dự toán', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Vật tư')
    quantity = fields.Float('Số lượng', default=1.0)
    price_unit = fields.Monetary('Đơn giá', required=True, currency_field='currency_id')
    price_subtotal = fields.Monetary(
        'Thành tiền',
        compute='_compute_price_subtotal',
        store=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        related='cost_estimate_id.currency_id',
        readonly=True,
        store=True
    )

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for rec in self:
            rec.price_subtotal = rec.quantity * rec.price_unit
