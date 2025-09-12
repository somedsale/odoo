from odoo import models, fields

class ProductMaterialLine(models.Model):
    _inherit = 'product.material.line'

    estimate_line_id = fields.Many2one(
        'cost.estimate.line',
        string='Dòng dự toán',
        ondelete='cascade',
        required=True
    )
