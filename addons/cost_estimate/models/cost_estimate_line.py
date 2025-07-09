from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class CostEstimateLine(models.Model):
    _name = 'cost.estimate.line'
    _description = 'Chi tiết dự toán'

    cost_estimate_id = fields.Many2one('cost.estimate', string='Dự toán', ondelete='cascade', required=True)
    product_id = fields.Many2one('product.product', string='Sản phẩm', ondelete='restrict', required=True)
    quantity = fields.Float('Số lượng', default=1.0, required=True)
    unit = fields.Many2one('uom.uom', string='Đơn vị')
    price_subtotal = fields.Float(
        string='Thành tiền',
        compute='_compute_price_subtotal',
        store=True,
        digits=(16, 0)
    )
    material_line_ids = fields.One2many(
        'product.material.line',
        'estimate_line_id',
        string='Dòng vật tư'
    )
    sale_order_line_id = fields.Many2one('sale.order.line', string="Dòng báo giá gốc")
    is_from_sale_order = fields.Boolean(string='Từ báo giá', compute='_compute_is_from_sale_order')
    @api.depends('sale_order_line_id')
    def _compute_is_from_sale_order(self):
        for line in self:
            line.is_from_sale_order = bool(line.sale_order_line_id)

    @api.depends('material_line_ids.price_total', 'quantity')
    def _compute_price_subtotal(self):
        for rec in self:
            # Tổng tiền vật tư của 1 sản phẩm * số lượng sản phẩm
            material_total = sum(line.price_total for line in rec.material_line_ids if line.exists())
            rec.price_subtotal = material_total * rec.quantity
            _logger.debug(
                "Computed price_subtotal for cost.estimate.line %s: %s (material_total=%s x quantity=%s)",
                rec.id, rec.price_subtotal, material_total, rec.quantity
            )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit = self.product_id.uom_id
        else:
            self.unit = False



