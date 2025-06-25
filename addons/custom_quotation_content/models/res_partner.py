from odoo import models
import logging
_logger = logging.getLogger(__name__)
class ResPartner(models.Model):
    _inherit = 'res.partner'

    def name_get(self):
        result = []
        for partner in self:
            name = partner.name or ''
            result.append((partner.id, name))
        return result
