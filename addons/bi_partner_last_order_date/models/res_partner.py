# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _
from datetime import datetime, timedelta


class ResPartner(models.Model):
    _inherit = 'res.partner'

    last_sale_order_date = fields.Date(compute="_compute_last_sale_order_date")
    last_purchase_order_date = fields.Date(compute="_compute_last_purchase_order_date")

    def _compute_last_sale_order_date(self):
        for rec in self:
            sale_order = self.env['sale.order'].sudo().search([('partner_id','=',rec.id)],order='id desc',limit=1)
            if sale_order:
                rec.last_sale_order_date = sale_order.date_order.date()
            else:
                rec.last_sale_order_date = False

    def _compute_last_purchase_order_date(self):
        for rec in self:
            purchase_order = self.env['purchase.order'].sudo().search([('partner_id','=',rec.id)],order='id desc',limit=1)
            if purchase_order:
                rec.last_purchase_order_date = purchase_order.date_order.date()
            else:
                rec.last_purchase_order_date = False