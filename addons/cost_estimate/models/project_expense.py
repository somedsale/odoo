from odoo import models, fields

class ProjectExpense(models.Model):
    _name = 'project.expense'
    _description = 'Danh mục Chi phí'

    name = fields.Char(string='Tên chi phí', required=True)
    default_unit = fields.Many2one('uom.uom', string='Đơn vị mặc định', required=True)
    type = fields.Selection([
    ('labor', 'Chi phí nhân công'),
    ('equipment', 'Chi phí máy móc'),
    ('other', 'Chi phí khác'),
], default='other')
    price_unit = fields.Float(string='Đơn giá', digits='Product Price', default=0.0)
