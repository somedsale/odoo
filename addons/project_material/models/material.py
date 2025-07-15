from odoo import models, fields, api

class ProjectMaterial(models.Model):
    _name = 'project.material'
    _description = 'Vật tư dự án'

    name = fields.Char(string='Tên vật tư', required=True)
    code = fields.Char(string='Mã vật tư')
    description = fields.Text(string='Mô tả')
    unit = fields.Many2one('uom.uom', string='Đơn vị', required=True)
    category_id = fields.Many2one('material.category', string='Danh mục')
    price_unit = fields.Float(string='Đơn giá', digits=(16, 0), default=0.0)

    @api.model
    def create(self, vals):
        if not vals.get('code'):
            # Lấy mã danh mục từ category_id
            category = self.env['material.category'].browse(vals.get('category_id'))
            category_code = category.code if category else 'UNK'
            # Lấy số sequence
            sequence = self.env['ir.sequence'].next_by_code('project.material.code') or '000'
            # Tạo mã theo quy tắc: Mã danh mục + Số sequence
            vals['code'] = f"{category_code}{sequence}"
        return super(ProjectMaterial, self).create(vals)
