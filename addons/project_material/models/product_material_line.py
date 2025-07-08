from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class ProductMaterialLine(models.Model):
    _name = 'product.material.line'
    _description = 'Product Material Line'

    product_id = fields.Many2one('product.product', string='Sản phẩm', ondelete='restrict')
    material_id = fields.Many2one('project.material', string='Vật tư', required=True)
    quantity = fields.Float(string='Số lượng', default=1.0)
    unit = fields.Many2one('uom.uom', string='Đơn vị', required=True)
    price_unit = fields.Float(string='Đơn giá', digits=(16, 0), default=0.0)
    price_total = fields.Float(
        string='Thành tiền',
        compute='_compute_price_total',
        store=True,
        digits=(16, 0)
    )

    @api.depends('price_unit', 'quantity')
    def _compute_price_total(self):
        for rec in self:
            rec.price_total = rec.price_unit * rec.quantity
            _logger.debug("Computed price_total for product.material.line %s: %s", rec.id, rec.price_total)

    @api.onchange('material_id')
    def _onchange_material_id(self):
        if self.material_id:
            self.unit = self.material_id.unit
            self.price_unit = 0.0
        else:
            self.unit = False
            self.price_unit = 0.0

