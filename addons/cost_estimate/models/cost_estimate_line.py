from odoo import models, fields, api

class CostEstimateLine(models.Model):
    _name = 'cost.estimate.line'
    _description = 'Chi tiết dự toán'

    cost_estimate_id = fields.Many2one('cost.estimate', string='Dự toán', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Sản phẩm', ondelete='set null')
    quantity = fields.Float('Số lượng', default=1.0)
    price_subtotal = fields.Monetary(
    'Thành tiền',
    compute='_compute_price_subtotal',
    store=True,
    currency_field='currency_id'
)
    currency_id = fields.Many2one('res.currency', related='cost_estimate_id.currency_id', store=True, readonly=True)
    unit = fields.Many2one('uom.uom', string='Đơn vị')

    @api.depends('product_id')
    def _compute_price_subtotal(self):
        for rec in self:
            if rec.product_id:
                material_lines = rec.env['product.material.line'].search([
                    ('product_id', '=', rec.product_id.id)
                ])
                rec.price_subtotal = sum(line.price_total for line in material_lines)
            else:
                rec.price_subtotal = 0.0
    def open_material_list(self):
        self.ensure_one()
        return {
            'name': 'Danh sách vật tư - %s' % self.product_id.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'product.material.line',
            'view_mode': 'tree,form',
            'domain': [('product_id', '=', self.product_id.id)],
            'context': {
                'default_product_id': self.product_id.id,
            },
            'target': 'current',
        }
    material_line_ids = fields.One2many(
        'product.material.line',
        'estimate_line_id',
        string='Dòng vật tư'
    )
