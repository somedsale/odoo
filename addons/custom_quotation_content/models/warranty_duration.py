from odoo import models, fields

class WarrantyDuration(models.Model):
    _name = 'warranty.duration'
    _description = 'Warranty Duration Options'

    name = fields.Text(string="Thời hạn bảo hành", required=True)
    description = fields.Text(string="Mô tả")