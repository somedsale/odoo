# -*- coding: utf-8 -*-
from odoo import models, _

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        res = super().button_validate()
        for picking in self:
            if picking.picking_type_code != 'incoming':
                continue
            orders = picking.move_ids_without_package.mapped('purchase_line_id.order_id')
            for po in set(orders):
                if po.exists() and po.shipping_status != 'done':
                    po.shipping_status = 'done'
                    po.message_post(body=_("Đã nhận hàng: Trạng thái hàng hóa chuyển sang <b>Đã giao</b>."))
        return res
