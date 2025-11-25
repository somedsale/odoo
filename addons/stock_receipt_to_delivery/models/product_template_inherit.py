# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Chỉ override default (không cần selection_add)
    detailed_type = fields.Selection(default='product')
