# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockMove(models.Model):
    _inherit = 'stock.move'


    # Project propagated from related MO (finished or raw material moves)
    project_id = fields.Many2one('project.project', string='Dự án',
    compute='_compute_project_id', store=True, index=True)


    @api.depends('production_id', 'raw_material_production_id',
    'production_id.project_id', 'raw_material_production_id.project_id')
    def _compute_project_id(self):
        for m in self:
            proj = m.production_id.project_id or m.raw_material_production_id.project_id
            m.project_id = proj.id if proj else False


    @api.onchange('project_id')
    def _onchange_project_product_domain(self):
        domain = {}
        if self.project_id and self.project_id.sale_product_ids:
            domain['product_id'] = [('id', 'in', self.project_id.sale_product_ids.ids)]
        return {'domain': domain}