from odoo import models, fields

class SmdDocumentTag(models.Model):
    _name = 'smd.document.tag'
    _description = 'Document Tag'
    _order = 'name'

    name = fields.Char('Tag Name', required=True)
    color = fields.Integer('Color Index')
    active = fields.Boolean(default=True)
