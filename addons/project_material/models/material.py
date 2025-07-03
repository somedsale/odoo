from odoo import models, fields

class ProjectMaterial(models.Model):
    _name = 'project.material'
    _description = 'Vật tư dự án'

    name = fields.Char(string='Tên vật tư', required=True)
    code = fields.Char(string='Mã vật tư')
    description = fields.Text(string='Mô tả')
