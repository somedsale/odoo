from odoo import models, fields, api


class TeamTodo(models.Model):
    _name = "team.todo"
    _description = "Công việc / Checklist nội bộ"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, deadline asc"

    # ==== Thông tin cơ bản ====
    name = fields.Char("Tên công việc", required=True)
    note = fields.Text("Chi tiết / Nội dung công việc")
    
    assigned_ids = fields.Many2many(
        "res.users", string="Người được giao"
    )

    deadline = fields.Date("Hạn hoàn thành")
    priority = fields.Selection([
    ("0", "Không có"),
    ("1", "Thấp"),
    ("2", "Bình Thường"),
    ("3", "Cao")
], string="Mức ưu tiên", default="1")

    # ==== Trạng thái công việc ====
    state = fields.Selection(
        [
            ("new", "Mới"),
            ("progress", "Đang làm"),
            ("done", "Hoàn tất"),
            ("cancel", "Hủy"),
        ],
        string="Trạng thái",
        default="new",
        group_expand="_expand_states",
    )

    # ==== Checklist con ====
    checklist_item_ids = fields.One2many(
        "team.todo.item", "todo_id", string="Checklist"
    )

    progress = fields.Float(
        "Tiến độ (%)", compute="_compute_progress", store=True, group_operator="avg"
    )

    # ============================================================

    @api.model
    def _expand_states(self, states, domain, order):
        """Hiển thị đầy đủ 4 cột Kanban"""
        return ["new", "progress", "done", "cancel"]

    @api.depends("checklist_item_ids.state")
    def _compute_progress(self):
        """Tính % tiến độ checklist"""
        for rec in self:
            total = len(rec.checklist_item_ids)
            done = len(rec.checklist_item_ids.filtered(lambda x: x.state == "done"))
            rec.progress = (done / total * 100) if total else 0

    @api.onchange("checklist_item_ids.state")
    def _auto_update_state(self):
        """Nếu tất cả checklist done thì tự chuyển sang hoàn tất"""
        for rec in self:
            if rec.checklist_item_ids and all(
                i.state == "done" for i in rec.checklist_item_ids
            ):
                rec.state = "done"
