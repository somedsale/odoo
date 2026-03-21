from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_vendor = fields.Boolean(
        string="Là nhà cung cấp",
        compute="_compute_is_vendor",
        inverse="_inverse_is_vendor",
        store=True,
    )

    @api.depends("supplier_rank")
    def _compute_is_vendor(self):
        for partner in self:
            partner.is_vendor = bool(partner.supplier_rank > 0)

    def _inverse_is_vendor(self):
        for partner in self:
            if partner.is_vendor:
                if partner.supplier_rank <= 0:
                    partner.supplier_rank = 1
            else:
                partner.supplier_rank = 0