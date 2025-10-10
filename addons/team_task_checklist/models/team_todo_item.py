from odoo import models, fields


class TeamTodoItem(models.Model):
    _name = "team.todo.item"
    _description = "Checklist chi tiết (giao từng người)"
    _order = "sequence, id"

    todo_id = fields.Many2one(
        "team.todo", string="Công việc tổng", ondelete="cascade", required=True
    )
    name = fields.Char("Hạng mục công việc", required=True)
    assigned_id = fields.Many2one("res.users", string="Người phụ trách")
    deadline = fields.Date("Hạn mục này cần xong trước")
    state = fields.Selection(
        [("todo", "Cần làm"), ("done", "Hoàn tất")],
        string="Trạng thái",
        default="todo",
        required=True,
    )
    completed_date = fields.Date("Ngày hoàn tất")
    sequence = fields.Integer(default=10)

    def action_toggle(self):
        """Chuyển nhanh trạng thái giữa ToDo / Done"""
        for rec in self:
            if rec.state == "done":
                rec.write({"state": "todo", "completed_date": False})
            else:
                rec.write({"state": "done", "completed_date": fields.Date.today()})
