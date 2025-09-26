from odoo import models, fields

class EstimateItemOther(models.Model):
    _name = "estimate.item.other"
    _description = "Other Estimate Item"

    name = fields.Char("Tên lựa chọn", required=True)
    description = fields.Text("Mô tả thêm")
    active = fields.Boolean(default=True)
