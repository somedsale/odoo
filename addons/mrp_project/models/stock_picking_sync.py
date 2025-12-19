# -*- coding: utf-8 -*-
from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _sync_multi_mrp_orders_done(self):
        orders = self.env["multi.mrp.order"].search([
            "|",
            ("picking_raw_id", "in", self.ids),
            ("picking_finished_id", "in", self.ids),
        ])
        if orders:
            orders._try_set_done_if_pickings_done()

    def write(self, vals):
        res = super().write(vals)

        # Bắt mọi trường hợp picking chuyển sang done (validate có/không wizard đều đi qua đây)
        if vals.get("state") == "done":
            self.filtered(lambda p: p.state == "done")._sync_multi_mrp_orders_done()

        return res
