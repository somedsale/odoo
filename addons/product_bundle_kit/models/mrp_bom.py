from odoo import models, api, fields


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    @api.model
    def create_bom_from_bundle(self, product):
        bundle = self.env["product.bundle"].search([("product_id", "=", product.id)], limit=1)
        if not bundle:
            return False

        bom = self.create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "type": "normal",
        })

        for line in bundle.line_ids:
            self.env["mrp.bom.line"].create({
                "bom_id": bom.id,
                "product_id": line.product_id.id,
                "product_qty": line.quantity,
            })

        return bom
