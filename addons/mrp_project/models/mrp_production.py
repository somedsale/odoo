# -*- coding: utf-8 -*-
from odoo import models, fields, api


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    project_id = fields.Many2one(
        'project.project',
        string='Dự án',
        index=True,
        help='Gắn Lệnh sản xuất với một Dự án.'
    )

    sale_product_ids = fields.Many2many(
        'product.product',
        string='Sản phẩm đơn bán',
        related='project_id.sale_product_ids',
        readonly=True
    )

    @api.onchange('project_id')
    def _onchange_project_id_set_product_domain(self):
        """Cập nhật domain cho product_id và bom_id khi chọn dự án."""
        domain = {}
        if self.project_id and self.project_id.sale_product_ids:
            product_ids = self.project_id.sale_product_ids.ids
            domain['product_id'] = [('id', 'in', product_ids)]
            domain['bom_id'] = [
                '|',
                ('product_tmpl_id.product_variant_ids', 'in', product_ids),
                ('product_id', 'in', product_ids),
            ]
            # Nếu product hiện tại không còn hợp lệ, xóa nó
            if self.product_id and self.product_id.id not in product_ids:
                self.product_id = False
        else:
            domain['product_id'] = [('id', '!=', False)]
            domain['bom_id'] = [('id', '!=', False)]
        return {'domain': domain}
