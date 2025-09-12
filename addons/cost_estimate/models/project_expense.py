from odoo import models, fields,api

class ProjectExpense(models.Model):
    _name = 'project.expense'
    _description = 'Danh mục Chi phí'

    name = fields.Char(string='Tên chi phí', required=True)
    default_unit = fields.Many2one('uom.uom', string='Đơn vị mặc định', required=True)
    type = fields.Selection([
    ('labor', 'Chi phí nhân công'),
    # ('equipment', 'Chi phí máy móc'),
    ('other', 'Chi phí sản xuất chung'),
], default='other', string='Loại chi phí', required=True)
    price_unit = fields.Float(string='Đơn giá', digits='Product Price', default=0.0)
    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.context.get('default_type'):
            res['type'] = self.env.context['default_type']
        return res
