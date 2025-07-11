from odoo import models, fields, api

class MaterialRequestLine(models.Model):
    _name = 'material.request.line'
    _description = 'Chi tiết vật tư đề xuất'

    request_id = fields.Many2one('material.request', string='Đề xuất', required=True, ondelete='cascade')
    material_id = fields.Many2one('project.material', string='Vật tư', required=True)
    quantity = fields.Float(string='Số lượng', default=1.0)
    unit = fields.Many2one('uom.uom', string='Đơn vị', required=True)
    price_unit = fields.Float(string='Đơn giá thực tế')
    description = fields.Text(string='Ghi chú')
  

    @api.onchange('material_id')
    def _onchange_material_id(self):
        if self.material_id:
            self.unit = self.material_id.unit.id
        else:
            self.unit = False