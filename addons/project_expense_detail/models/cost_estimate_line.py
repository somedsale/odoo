from odoo import models, fields, api
class CostEstimateLine(models.Model):
    _inherit = 'cost.estimate.line'
   

    name = fields.Char(string="Đầu mục")
    @api.model
    def create(self, vals):
        if not vals.get('name'):
            product_name = ""
            if vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                product_name = product.display_name
            vals['name'] = product_name or "Không có mô tả"
        return super().create(vals)