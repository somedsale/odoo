# models/project_task_inherit.py
from odoo import models, fields, api, _

class ProjectTask(models.Model):
    _inherit = "project.task"

    purchase_order_count = fields.Integer(
        string="Số PO",
        compute="_compute_purchase_order_count",
    )

    def _compute_purchase_order_count(self):
        PurchaseOrder = self.env["purchase.order"]
        for task in self:
            # Đếm PO có liên kết proposal_sheet_id, mà proposal đó thuộc task này
            task.purchase_order_count = PurchaseOrder.search_count([
                ("proposal_sheet_id.task_id", "=", task.id)
            ])

    def action_view_task_purchase_orders(self):
        """Mở các PO liên quan đến task này (thông qua proposal.sheet)."""
        self.ensure_one()
        action = self.env.ref("purchase.purchase_form_action").read()[0]
        # Dùng dot-notation để lọc qua M2O: purchase.order -> proposal_sheet_id -> task_id
        action["domain"] = [("proposal_sheet_id.task_id", "=", self.id)]
        # Tuỳ chọn context: group theo NCC, điền origin mặc định…
        action["context"] = {
            "search_default_groupby_partner": 1,
            "default_origin": self.name,
        }
        return action
