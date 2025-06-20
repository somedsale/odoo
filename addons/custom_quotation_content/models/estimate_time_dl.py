from odoo import fields, models
class EstimatedDeliveryTime(models.Model):
    _name = 'estimated.delivery.time'
    _description = 'Estimated Delivery Time Options'
 
    name = fields.Char(string="Tùy chọn", required=True)
    description = fields.Text(string="Mô tả")