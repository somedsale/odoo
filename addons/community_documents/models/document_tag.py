# -*- coding: utf-8 -*-
from odoo import fields, models


class DocumentTag(models.Model):
    _name = "document.tag"
    _description = "Document Tag"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    color = fields.Integer(default=0)
