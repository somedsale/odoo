# models/stock_move_line.py
from odoo import models, fields, api

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    # related để có cột Dự án trên move line (nhanh cho search/group)
    project_id = fields.Many2one(
        'project.project',
        string='Dự án',
        related='move_id.project_id',
        store=True,
        index=True,
        readonly=True,
    )

    @api.onchange('move_id')
    def _onchange_move_set_product_domain(self):
        domain = {}
        proj = self.move_id.project_id
        if proj and proj.sale_product_ids:
            domain['product_id'] = [('id', 'in', proj.sale_product_ids.ids)]
        return {'domain': domain}
