from odoo import models, fields,api
from odoo.tools import format_amount
class ProductMaterialLine(models.Model):
    _name = 'product.material.line'
    _description = 'Product Material Line'
    
    product_id = fields.Many2one('product.product', string='Sản phẩm')
    material_id = fields.Many2one('project.material', string='Vật tư')
    quantity = fields.Float(string='Số lượng')
    unit = fields.Many2one('uom.uom', string='Đơn vị', required=True)
    price_unit = fields.Float(
        string='Đơn giá',
        digits=(16, 0),  # Không có số thập phân
        default=0.0
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        default=lambda self: self.env.company.currency_id,
        required=True
    )

    price_unit_display = fields.Char(
        string='Đơn giá (hiển thị)',
        compute='_compute_price_unit_display'
    )

    @api.depends('price_unit', 'currency_id')
    def _compute_price_unit_display(self):
       for rec in self:
           if rec.currency_id:
               rec.price_unit_display = format_amount(
                   rec.env,
                   rec.price_unit,
                   rec.currency_id
               )
           else:
               rec.price_unit_display = '{:,.0f}₫'.format(rec.price_unit).replace(',', '.')

    @api.onchange('material_id')
    def _onchange_material_id(self):
        if self.material_id and self.material_id.unit:
            self.unit = self.material_id.unit