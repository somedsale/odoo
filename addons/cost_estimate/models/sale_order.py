from odoo import models, api, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cost_estimate_id = fields.Many2one('cost.estimate', string='Dự toán chi phí', readonly=True)

