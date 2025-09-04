from odoo import models, fields
class ResCompany(models.Model):
    _inherit = "res.company"

    phone_accounting = fields.Char(string="Phone Accounting")
    phone_sale = fields.Char(string="Phone Sale")
    phone_manufacturing = fields.Char(string="Phone Manufacturing")


   


