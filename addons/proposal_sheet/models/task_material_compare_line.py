from odoo import models, fields, api
class TaskMaterialCompareLine(models.TransientModel):  # dùng TransientModel vì không lưu DB
    _name = 'task.material.compare.line'
    _description = 'So sánh vật tư dự toán và thực tế'

    material_id = fields.Many2one('project.material', string='Vật tư')
    estimated_qty = fields.Float(string='Dự toán')
    actual_qty = fields.Float(string='Đã duyệt')
    difference = fields.Float(string='Chênh lệch')
    note = fields.Char(string='Ghi chú')
