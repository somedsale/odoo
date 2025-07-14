from odoo import models, fields,api

class MaterialCategory(models.Model):
    _name = 'material.category'
    _description = 'Danh mục vật tư'

    name = fields.Char(string='Tên danh mục', required=True)
    code = fields.Char(string='Mã danh mục')
    description = fields.Text(string='Mô tả')
    @api.model
    def create(self, vals):
        if 'name' in vals and not vals.get('code'):
            # Tách các từ trong name và lấy ký tự đầu tiên của từng từ
            words = vals['name'].strip().split()
            code = ''.join(word[0].upper() for word in words if word)
            vals['code'] = code
        return super().create(vals)
