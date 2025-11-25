# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProjectProject(models.Model):
    _inherit = 'project.project'


    # Products belonging to the Sale Order of this project (stored for fast domain/group)
    sale_product_ids = fields.Many2many(
    'product.product', string='Sản phẩm đơn bán',
    compute='_compute_sale_product_ids', store=True)


    @api.depends('sale_order_id', 'sale_order_id.order_line.product_id')
    def _compute_sale_product_ids(self):
        for p in self:
            if p.sale_order_id:
                p.sale_product_ids = [(6, 0, p.sale_order_id.order_line.mapped('product_id').ids)]
        else:
            p.sale_product_ids = [(5, 0, 0)]