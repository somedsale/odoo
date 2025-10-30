from odoo import models, fields, api
class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_lender = fields.Boolean(string='Là bên cho vay',default=False)
