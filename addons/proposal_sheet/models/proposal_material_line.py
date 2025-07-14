from odoo import models, fields, api

class ProposalMaterialLine(models.Model):
    _name = 'proposal.material.line'
    _description = 'Chi tiết vật tư'

    sheet_id = fields.Many2one('proposal.sheet', string='Phiếu đề xuất', required=True, ondelete='cascade')
    material_id = fields.Many2one('project.material', string='Vật tư', required=True)
    quantity = fields.Float(string='Số lượng', default=1.0)
    unit = fields.Many2one('uom.uom', string='Đơn vị', required=True)
    price_unit = fields.Float(string='Đơn giá thực tế')
    description = fields.Text(string='Ghi chú')
    type = fields.Selection(selection=[('material', 'Vật tư')], default='material', required=True)


    @api.onchange('material_id')
    def _onchange_material_id(self):
        if self.material_id:
            self.unit = self.material_id.unit.id
        else:
            self.unit = False
