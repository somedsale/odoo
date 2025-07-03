from odoo import models, fields
class ProductMaterialLine(models.Model):
    _name = 'product.material.line'
    _description = 'Product Material Line'
    
    product_id = fields.Many2one('product.product', string='Sản phẩm')
    material_id = fields.Many2one('product.product', string='Vật tư')
    quantity = fields.Float(string='Số lượng')
