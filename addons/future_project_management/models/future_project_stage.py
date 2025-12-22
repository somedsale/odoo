from odoo import models, fields

class FutureProjectStage(models.Model):
    _name = "future.project.stage"
    _description = "Future Project Stage"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean("Folded in Kanban")
    probability = fields.Float("Xác xuất (%)", default=0.0)
