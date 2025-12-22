from odoo import models, fields, api
class FutureProjectLocation(models.Model):
    _name = "future.project.location"
    _description = "Future Project Location"

    name = fields.Char("Tên khu vực", required=True)
    description = fields.Text("Mô tả")