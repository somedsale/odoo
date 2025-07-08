from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class CostEstimateLine(models.Model):
    _name = 'cost.estimate.line'
    _description = 'Chi tiết dự toán'

    cost_estimate_id = fields.Many2one('cost.estimate', string='Dự toán', ondelete='cascade', required=True)
    product_id = fields.Many2one('product.product', string='Sản phẩm', ondelete='restrict', required=True)
    quantity = fields.Float('Số lượng', default=1.0, required=True)
    unit = fields.Many2one('uom.uom', string='Đơn vị')
    price_subtotal = fields.Float(
        string='Thành tiền',
        compute='_compute_price_subtotal',
        store=True,
        digits=(16, 0)
    )
    material_line_ids = fields.One2many(
        'product.material.line',
        'estimate_line_id',
        string='Dòng vật tư'
    )


    @api.depends('material_line_ids.price_total')
    def _compute_price_subtotal(self):
        for rec in self:
            rec.price_subtotal = sum(line.price_total for line in rec.material_line_ids if line.exists())
            _logger.debug("Computed price_subtotal for cost.estimate.line %s: %s", rec.id, rec.price_subtotal)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit = self.product_id.uom_id
        else:
            self.unit = False
    def open_material_list(self):
        self.ensure_one()
        if not self.id:
            raise UserError("Vui lòng lưu dòng dự toán trước khi mở danh sách vật tư.")
        return {
            'name': 'Danh sách vật tư - %s' % (self.product_id.display_name or 'Không có sản phẩm'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.material.line',
            'view_mode': 'tree,form',
            'domain': [('estimate_line_id', '=', self.id)],
            'context': {
                'default_estimate_line_id': self.id,
                'default_product_id': self.product_id.id,
                'default_unit': self.unit.id if self.unit else False,
            },
            'target': 'current',
        }


