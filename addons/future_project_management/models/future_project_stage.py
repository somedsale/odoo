from odoo import models, fields

class FutureProjectStage(models.Model):
    _name = "future.project.stage"
    _description = "Future Project Stage"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean("Folded in Kanban")
    probability = fields.Float("Probability (%)", default=0.0)

    is_won = fields.Boolean(
        string="Trúng thầu",
        help="Dự án ở stage này được xem là trúng thầu",
    )

    is_lost = fields.Boolean(
        string="Không khả thi",
        help="Dự án ở stage này sẽ bị bỏ theo dõi",
    )
